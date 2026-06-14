from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import uuid
import webbrowser
from collections import Counter
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from html import unescape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ARMOR_SET_RATINGS_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "14LnzOhmeXzKaSV3OR35pQJkclg6vLC4YmKtlKTctY3o/export?format=csv&gid=631213508"
)
DESTINY_REPORT_URL = "https://destiny.report/"


@dataclass(frozen=True)
class CachedSource:
    label: str
    path: Path
    args: tuple[str, str]


@dataclass
class WizardRun:
    run_id: str
    run_dir: Path
    upload_paths: list[Path]
    config_args: list[str]
    source_args: list[str]


class WizardState:
    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.runs_dir = root / ".dva" / "wizard-runs"
        self.runs: dict[str, WizardRun] = {}
        self.lock = threading.Lock()

    def create_run(self, uploads: list[tuple[str, bytes]], config_args: list[str]) -> WizardRun:
        run_id = uuid.uuid4().hex[:12]
        run_dir = self.runs_dir / run_id
        upload_dir = run_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_paths: list[Path] = []
        for index, (filename, payload) in enumerate(uploads, start=1):
            safe_name = _safe_filename(filename, index)
            path = upload_dir / safe_name
            path.write_bytes(payload)
            upload_paths.append(path)

        source_args = _source_args(self.root)
        run = WizardRun(
            run_id=run_id,
            run_dir=run_dir,
            upload_paths=upload_paths,
            config_args=config_args,
            source_args=source_args,
        )
        with self.lock:
            self.runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> WizardRun | None:
        with self.lock:
            return self.runs.get(run_id)


def start_wizard(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    server = create_wizard_server(host, port)
    url = f"http://{server.server_address[0]}:{server.server_address[1]}/"
    print(f"Destiny Vault Auditor wizard running at {url}")
    print("Press Ctrl-C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping wizard.")
    finally:
        server.server_close()


def create_wizard_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    state = WizardState()

    class Handler(WizardRequestHandler):
        wizard_state = state

    return ThreadingHTTPServer((host, port), Handler)


class WizardRequestHandler(BaseHTTPRequestHandler):
    wizard_state: WizardState
    server_version = "DestinyVaultAuditorWizard/1.0"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(_wizard_html())
            return
        if path == "/api/sources":
            self._send_json({"sources": _source_states(self.wizard_state.root)})
            return
        if path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/audit":
            self._handle_audit()
            return
        if path == "/api/export-dim":
            self._handle_export_dim()
            return
        if path == "/api/refresh-sources":
            self._handle_refresh_sources()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: object) -> None:
        print(f"[wizard] {self.address_string()} - {format % args}")

    def _handle_audit(self) -> None:
        try:
            fields, uploads = self._read_multipart()
            if not uploads:
                self._send_json({"error": "Choose one or two DIM CSV exports first."}, HTTPStatus.BAD_REQUEST)
                return
            config_args = _config_args_from_fields(fields)
            run = self.wizard_state.create_run(uploads, config_args)
            result = _run_audit(run)
        except WizardError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as error:  # pragma: no cover - keeps local server failures readable.
            self._send_json({"error": f"Wizard failed: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._send_json(result)

    def _handle_export_dim(self) -> None:
        try:
            payload = self._read_json()
            run_id = str(payload.get("run_id") or "")
            run = self.wizard_state.get_run(run_id)
            if not run:
                self._send_json({"error": "That audit session is no longer available. Run the audit again."}, HTTPStatus.BAD_REQUEST)
                return
            recommendations = payload.get("recommendations")
            if not isinstance(recommendations, list):
                self._send_json({"error": "Export payload is missing reviewed recommendations."}, HTTPStatus.BAD_REQUEST)
                return
            review_path = run.run_dir / "reviewed-decisions.json"
            review_path.write_text(
                json.dumps(
                    {
                        "schema": "destiny-vault-auditor.review.v1",
                        "recommendations": recommendations,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            final_dir = run.run_dir / "final"
            _run_audit(run, out_dir=final_dir, review_decisions_json=review_path)
            csv_bytes = (final_dir / "dim-import.csv").read_bytes()
        except WizardError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as error:  # pragma: no cover - keeps local server failures readable.
            self._send_json({"error": f"Export failed: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="dim-import.csv"')
        self.send_header("Content-Length", str(len(csv_bytes)))
        self.end_headers()
        self.wfile.write(csv_bytes)

    def _handle_refresh_sources(self) -> None:
        try:
            refreshed = _refresh_sources(self.wizard_state.root)
        except WizardError as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as error:  # pragma: no cover - keeps local server failures readable.
            self._send_json({"error": f"Source refresh failed: {error}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._send_json({"refreshed": refreshed, "sources": _source_states(self.wizard_state.root)})

    def _read_multipart(self) -> tuple[dict[str, str], list[tuple[str, bytes]]]:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise WizardError("Expected multipart form data.")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        message = BytesParser(policy=policy.default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
        )
        fields: dict[str, str] = {}
        uploads: list[tuple[str, bytes]] = []
        for part in message.iter_parts():
            disposition = part.get("Content-Disposition", "")
            if "form-data" not in disposition:
                continue
            name = part.get_param("name", header="Content-Disposition") or ""
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                if payload:
                    uploads.append((filename, payload))
            else:
                fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return fields, uploads

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError as error:
            raise WizardError(f"Invalid JSON: {error}") from error
        if not isinstance(payload, dict):
            raise WizardError("Expected a JSON object.")
        return payload

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class WizardError(Exception):
    pass


def _run_audit(run: WizardRun, out_dir: Path | None = None, review_decisions_json: Path | None = None) -> dict[str, object]:
    audit_out_dir = out_dir or (run.run_dir / "audit")
    cmd = [
        sys.executable,
        "-m",
        "auditor.cli",
        *(str(path) for path in run.upload_paths),
        "--out-dir",
        str(audit_out_dir),
        *run.config_args,
        *run.source_args,
    ]
    if review_decisions_json:
        cmd.extend(["--review-decisions-json", str(review_decisions_json)])

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise WizardError(details or "Audit failed.")

    decisions = json.loads((audit_out_dir / "decisions.json").read_text(encoding="utf-8"))
    recommendations = decisions.get("recommendations") or []
    if not isinstance(recommendations, list):
        raise WizardError("Audit produced an invalid decisions file.")
    duplicate_summary = _duplicate_summary(recommendations)
    return {
        "run_id": run.run_id,
        "stdout": result.stdout,
        "config": decisions.get("config") or {},
        "sources": decisions.get("sources") or [],
        "recommendations": recommendations,
        "counts": _counts(recommendations),
        "duplicate_summary": duplicate_summary,
        "used_cached_sources": [arg for arg in run.source_args if not arg.startswith("--")],
    }


def _cached_sources(root: Path) -> list[CachedSource]:
    sources: list[CachedSource] = []
    for state in _source_states(root):
        if state["status"] != "cached":
            continue
        path = root / str(state["path"])
        if state["id"] == "armor_sets":
            sources.append(CachedSource(str(state["label"]), path, ("--armor-set-ratings-csv", str(path))))
        elif state["id"] == "destiny_report":
            sources.append(CachedSource(str(state["label"]), path, ("--destiny-report-json", str(path))))
        elif state["id"] == "wishlist":
            sources.append(CachedSource(str(state["label"]), path, ("--wishlist-source", str(path))))
    return sources


def _source_states(root: Path) -> list[dict[str, str]]:
    cache_dir = root / "source-cache"
    armor_sets = cache_dir / "armor-set-ratings.csv"
    destiny_report = _first_existing(
        [*sorted(cache_dir.glob("*destiny*report*.json")), *sorted(cache_dir.glob("destiny-report*.json"))]
    )
    wishlist = _first_existing([*sorted(cache_dir.glob("wishlist*.json")), *sorted(cache_dir.glob("wishlist*.csv"))])
    return [
        _source_state("armor_sets", "armor set rating sheet", armor_sets, root),
        _source_state("destiny_report", "destiny.report weapon metadata", destiny_report, root),
        _source_state("wishlist", "wishlist/triage source", wishlist, root),
    ]


def _source_state(source_id: str, label: str, path: Path | None, root: Path) -> dict[str, str]:
    if path and path.exists():
        state = {
            "id": source_id,
            "label": label,
            "status": "cached",
            "path": str(path.relative_to(root)),
        }
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            generated_at = str(payload.get("generatedAt") or "")
            if generated_at:
                state["detail"] = generated_at[:10]
        return state
    return {
        "id": source_id,
        "label": label,
        "status": "unavailable",
        "path": "",
        "detail": "not cached",
    }


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _refresh_sources(root: Path) -> list[dict[str, str]]:
    cache_dir = root / "source-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    refreshed: list[dict[str, str]] = []

    armor_path = cache_dir / "armor-set-ratings.csv"
    _download_to(ARMOR_SET_RATINGS_URL, armor_path)
    refreshed.append({"label": "armor set rating sheet", "path": str(armor_path.relative_to(root))})

    weapons_path = cache_dir / "destiny-report-weapons.json"
    weapons_url = _destiny_report_weapons_url()
    _download_to(weapons_url, weapons_path)
    payload = json.loads(weapons_path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("weapons"), dict):
        weapons_path.unlink(missing_ok=True)
        raise WizardError("destiny.report refresh did not return a weapons database.")
    refreshed.append({"label": "destiny.report weapon metadata", "path": str(weapons_path.relative_to(root))})
    return refreshed


def _destiny_report_weapons_url() -> str:
    with urlopen(DESTINY_REPORT_URL, timeout=30) as response:
        html_text = response.read().decode("utf-8", errors="replace")
    match = re.search(r'<script type="application/json" id="destiny-report-config">(.*?)</script>', html_text)
    if match:
        config = json.loads(unescape(match.group(1)))
        weapons_url = str(config.get("weaponsUrl") or "")
        if weapons_url:
            return _absolute_destiny_report_url(weapons_url)
    match = re.search(r'"(/assets/public/data/weapons\.[^"]+\.json)"', html_text)
    if match:
        return _absolute_destiny_report_url(match.group(1))
    raise WizardError("Could not find destiny.report weapon data URL.")


def _absolute_destiny_report_url(path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"https://destiny.report/{path_or_url.lstrip('/')}"


def _download_to(url: str, path: Path) -> None:
    with urlopen(url, timeout=60) as response:
        payload = response.read()
    path.write_bytes(payload)


def _source_args(root: Path) -> list[str]:
    args: list[str] = []
    for source in _cached_sources(root):
        args.extend(source.args)
    return args


def _config_args_from_fields(fields: dict[str, str]) -> list[str]:
    choices = {
        "cleanup_mode": {"gentle", "clean-slate", "aggressive"},
        "locked_behavior": {"protect", "review", "ignore"},
        "duplicate_pruning": {"keep-more", "balanced", "prune-hard"},
        "old_vs_new": {"keep-bridges", "balanced", "prefer-new"},
        "pvp_caution": {"cautious", "balanced", "strict"},
        "notes_behavior": {"respect", "ignore"},
    }
    args: list[str] = []
    for name, allowed in choices.items():
        value = fields.get(name, "").strip()
        if value and value in allowed:
            args.extend([f"--{name.replace('_', '-')}", value])
    return args


def _counts(recommendations: list[object]) -> dict[str, dict[str, int]]:
    bucket_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        bucket_counts[str(rec.get("bucket") or "")] += 1
        tag_counts[str(rec.get("tag") or "")] += 1
        kind_counts[str(rec.get("kind") or "")] += 1
    return {
        "bucket": dict(sorted(bucket_counts.items())),
        "tag": dict(sorted(tag_counts.items())),
        "kind": dict(sorted(kind_counts.items())),
    }


def _duplicate_summary(recommendations: list[object]) -> dict[str, int]:
    groups: set[str] = set()
    items = 0
    weapon_groups: set[str] = set()
    armor_groups: set[str] = set()
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        group = str(rec.get("duplicate_group") or "")
        if not group:
            continue
        items += 1
        groups.add(group)
        if rec.get("kind") == "weapon":
            weapon_groups.add(group)
        if rec.get("kind") == "armor":
            armor_groups.add(group)
    return {
        "groups": len(groups),
        "items": items,
        "weapon_groups": len(weapon_groups),
        "armor_groups": len(armor_groups),
    }


def _safe_filename(filename: str, index: int) -> str:
    stem = Path(filename).stem or f"dim-export-{index}"
    suffix = Path(filename).suffix.lower() or ".csv"
    if suffix != ".csv":
        suffix = ".csv"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-") or f"dim-export-{index}"
    return f"{index}-{safe_stem}{suffix}"


def _wizard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Destiny Vault Auditor</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #11100d; color: #f1eee8; }
    * { box-sizing: border-box; }
    body { margin: 0; background: #11100d; color: #f1eee8; }
    header { padding: 22px 28px 14px; border-bottom: 1px solid #373026; background: #181510; position: sticky; top: 0; z-index: 3; }
    h1 { margin: 0 0 12px; font-size: 24px; line-height: 1.15; }
    main { padding: 18px 28px 40px; display: grid; gap: 18px; }
    .panel { border: 1px solid #373026; background: #17140f; border-radius: 8px; padding: 16px; }
    .dropzone { display: grid; place-items: center; min-height: 156px; border: 1px dashed #76644d; border-radius: 8px; background: #1c1812; color: #d9c9b5; text-align: center; text-transform: none; letter-spacing: 0; cursor: pointer; }
    .dropzone:hover, .file-input:focus + .dropzone { border-color: #d9b56c; background: #221d12; outline: 2px solid #d9b56c; outline-offset: 3px; }
    .dropzone.dragging { border-color: #d9b56c; background: #221d12; }
    .dropzone strong { display: block; margin-bottom: 6px; color: #f1eee8; font-size: 18px; }
    .controls, .filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    .primary-controls { margin-top: 14px; justify-content: space-between; }
    .profile-control { flex: 1 1 260px; max-width: 420px; }
    .profile-control select { width: 100%; }
    .note-toggle { min-height: 44px; display: inline-flex; align-items: center; gap: 8px; color: #d9c9b5; text-transform: none; letter-spacing: 0; }
    .note-toggle input { accent-color: #d9b56c; }
    .advanced-rules { margin-top: 12px; color: #cfc4b5; }
    .advanced-rules summary { cursor: pointer; min-height: 44px; display: inline-flex; align-items: center; font-weight: 650; }
    .advanced-rules .controls { margin-top: 8px; }
    label { color: #cfc4b5; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; display: grid; gap: 5px; }
    input, select, button, textarea { background: #242018; color: #f1eee8; border: 1px solid #4c4234; border-radius: 6px; padding: 10px 12px; min-height: 44px; font: inherit; }
    input[type="checkbox"] { min-height: 0; width: 18px; height: 18px; }
    .file-input { position: absolute; min-height: 0; inline-size: 1px; block-size: 1px; overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); white-space: nowrap; }
    button { cursor: pointer; font-weight: 650; }
    button.primary { background: #d9b56c; border-color: #d9b56c; color: #16120d; }
    button:disabled { cursor: not-allowed; opacity: .55; }
    .sourcebar, .filelist, .stats, .queuebar { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip { border: 1px solid #4c4234; border-radius: 999px; color: #e6d6bd; padding: 4px 9px; font-size: 12px; }
    .chip.unavailable { color: #9e9387; border-color: #332c23; }
    .source-panel { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    .queue-btn[aria-pressed="true"] { background: #d9b56c; border-color: #d9b56c; color: #16120d; }
    .review-progress { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 8px 0 12px; color: #cfc4b5; }
    progress { accent-color: #d9b56c; inline-size: min(260px, 100%); }
    .muted { color: #a79b8c; }
    .status { min-height: 22px; color: #d9c9b5; }
    .audit-summary { margin-bottom: 12px; color: #e6d6bd; }
    .stat { min-width: 136px; border: 1px solid #373026; border-radius: 8px; padding: 11px; background: #1b1812; text-align: left; }
    .stat:hover { border-color: #d9b56c; }
    .stat[aria-pressed="true"] { background: #d9b56c; border-color: #d9b56c; color: #16120d; }
    .stat strong { display: block; font-size: 22px; }
    table { width: 100%; border-collapse: collapse; background: #17140f; border: 1px solid #373026; }
    th, td { padding: 10px; border-bottom: 1px solid #302a22; text-align: left; vertical-align: top; }
    th { color: #cfc4b5; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; background: #1d1912; position: sticky; top: 86px; z-index: 2; }
    tr[data-bucket="replace-now"], tr[data-bucket="junk"] { background: #241312; }
    tr[data-bucket="keep-refarm"] { background: #221d10; }
    tr[data-bucket="protect"] { background: #111d18; }
    .pill { display: inline-block; border: 1px solid #5a4c3c; border-radius: 999px; padding: 2px 8px; font-size: 12px; color: #e6d6bd; }
    .reason { color: #d4c8b8; max-width: 760px; }
    .signals { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 5px; }
    .signal { border: 1px solid #473d31; border-radius: 999px; padding: 1px 6px; font-size: 11px; color: #bdae9b; }
    .tag-edit { min-width: 100px; }
    .comment-edit { margin-top: 8px; width: min(100%, 780px); min-height: 58px; resize: vertical; line-height: 1.35; background: #14110d; }
    .hidden { display: none; }
    @media (max-width: 760px) {
      header, main { padding-left: 14px; padding-right: 14px; }
      th { position: static; }
      table, thead, tbody, tr, th, td { display: block; width: 100%; }
      thead { display: none; }
      tr { border-bottom: 1px solid #373026; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Destiny Vault Auditor</h1>
    <div class="sourcebar" id="sourcebar"></div>
  </header>
  <main>
    <section class="panel">
      <form id="audit-form">
        <input id="files" class="file-input" name="files" type="file" accept=".csv,text/csv" multiple aria-describedby="upload-help">
        <label class="dropzone" id="dropzone" for="files"><span><strong>Drop DIM exports here</strong><span id="upload-help">Weapons and armor CSVs are detected automatically.</span></span></label>
        <div class="filelist" id="filelist"></div>
        <div class="source-panel">
          <button id="refresh-sources" type="button">Refresh sources</button>
          <span class="muted" id="source-status">Uses cached local sources when available.</span>
        </div>
        <div class="controls primary-controls">
          <label class="profile-control">Audit style<select id="audit-profile" name="audit_profile"><option value="returning" selected>Returning Guardian</option><option value="cautious">Cautious</option><option value="deep-clean">Deep clean</option></select></label>
          <input id="notes-behavior" type="hidden" name="notes_behavior" value="respect">
          <label class="note-toggle"><input id="notes-behavior-toggle" type="checkbox" checked> Use existing DIM notes as intent</label>
          <button class="primary" id="run" type="submit">Run audit</button>
        </div>
        <details class="advanced-rules">
          <summary>Advanced rules</summary>
          <div class="controls">
            <label>Cleanup<select name="cleanup_mode"><option value="clean-slate">Clean slate</option><option value="gentle">Gentle</option><option value="aggressive">Aggressive</option></select></label>
            <label>Locked<select name="locked_behavior"><option value="review">Review</option><option value="protect">Protect</option><option value="ignore">Ignore</option></select></label>
            <label>Duplicates<select name="duplicate_pruning"><option value="balanced">Balanced</option><option value="keep-more">Keep more</option><option value="prune-hard">Prune hard</option></select></label>
            <label>Old rolls<select name="old_vs_new"><option value="balanced">Balanced</option><option value="keep-bridges">Keep bridges</option><option value="prefer-new">Prefer new</option></select></label>
            <label>PvP<select name="pvp_caution"><option value="balanced">Balanced</option><option value="cautious">Cautious</option><option value="strict">Strict</option></select></label>
          </div>
        </details>
      </form>
      <div class="status" id="status"></div>
    </section>
    <section class="panel hidden" id="results">
      <div class="audit-summary" id="audit-summary"></div>
      <div class="queuebar" id="queuebar" style="margin-bottom: 12px;"></div>
      <div class="controls" style="justify-content: space-between; margin-bottom: 12px;">
        <div class="filters">
          <input id="search" type="search" placeholder="Search gear or reasons">
          <select id="kind"><option value="">All gear</option></select>
          <select id="bucket"><option value="">All buckets</option></select>
          <select id="tag"><option value="">All tags</option></select>
        </div>
        <button id="approve-visible" type="button">Approve visible</button>
        <button class="primary" id="export" type="button">Export DIM import CSV</button>
      </div>
      <div class="stats" id="stats"></div>
      <div class="review-progress" id="review-progress"></div>
      <div class="muted" id="duplicate-summary" style="margin: 10px 0;"></div>
      <table>
        <thead><tr><th>Name</th><th>Bucket</th><th>Tag</th><th>Confidence</th><th>Reason and note</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </section>
  </main>
  <script>
    let selectedFiles = [];
    let audit = null;
    let activeQueue = '';
    const filesEl = document.getElementById('files');
    const dropzone = document.getElementById('dropzone');
    const filelist = document.getElementById('filelist');
    const form = document.getElementById('audit-form');
    const statusEl = document.getElementById('status');
    const sourceStatusEl = document.getElementById('source-status');
    const resultsEl = document.getElementById('results');
    const rowsEl = document.getElementById('rows');
    const statsEl = document.getElementById('stats');
    const queuebarEl = document.getElementById('queuebar');
    const searchEl = document.getElementById('search');
    const kindEl = document.getElementById('kind');
    const bucketEl = document.getElementById('bucket');
    const tagEl = document.getElementById('tag');
    const profileEl = document.getElementById('audit-profile');
    const auditSummaryEl = document.getElementById('audit-summary');
    const notesBehaviorEl = document.getElementById('notes-behavior');
    const notesBehaviorToggleEl = document.getElementById('notes-behavior-toggle');
    const presetRules = {
      'returning': {cleanup_mode: 'clean-slate', locked_behavior: 'ignore', duplicate_pruning: 'prune-hard', old_vs_new: 'prefer-new', pvp_caution: 'strict', notes_behavior: 'respect'},
      'cautious': {cleanup_mode: 'gentle', locked_behavior: 'protect', duplicate_pruning: 'keep-more', old_vs_new: 'keep-bridges', pvp_caution: 'cautious', notes_behavior: 'respect'},
      'deep-clean': {cleanup_mode: 'aggressive', locked_behavior: 'ignore', duplicate_pruning: 'prune-hard', old_vs_new: 'prefer-new', pvp_caution: 'strict', notes_behavior: 'ignore'}
    };

    function applyPreset() {
      const rules = presetRules[profileEl.value] || presetRules.returning;
      for (const [name, value] of Object.entries(rules)) {
        const field = form.elements[name];
        if (field) field.value = value;
      }
      notesBehaviorToggleEl.checked = notesBehaviorEl.value !== 'ignore';
    }
    profileEl.addEventListener('change', applyPreset);
    notesBehaviorToggleEl.addEventListener('change', () => {
      notesBehaviorEl.value = notesBehaviorToggleEl.checked ? 'respect' : 'ignore';
    });
    applyPreset();

    async function refreshSourceBadges() {
      const response = await fetch('/api/sources');
      const data = await response.json();
      const sources = data.sources || [];
      document.getElementById('sourcebar').innerHTML = sources.length
        ? sources.map(source => `<span class="chip ${source.status === 'cached' ? '' : 'unavailable'}">${escapeHtml(source.status)}: ${escapeHtml(source.label)}${source.detail ? ` · ${escapeHtml(source.detail)}` : ''}</span>`).join('')
        : '<span class="chip">DIM CSV only</span>';
    }
    refreshSourceBadges();
    document.getElementById('refresh-sources').addEventListener('click', async () => {
      const button = document.getElementById('refresh-sources');
      sourceStatusEl.textContent = 'Refreshing public source caches...';
      button.disabled = true;
      try {
        const response = await fetch('/api/refresh-sources', { method: 'POST' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Source refresh failed.');
        await refreshSourceBadges();
        sourceStatusEl.textContent = `Refreshed ${data.refreshed.length} sources.`;
      } catch (error) {
        sourceStatusEl.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });

    dropzone.addEventListener('click', () => filesEl.click());
    dropzone.addEventListener('dragover', event => { event.preventDefault(); dropzone.classList.add('dragging'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragging'));
    dropzone.addEventListener('drop', event => {
      event.preventDefault();
      dropzone.classList.remove('dragging');
      setFiles(Array.from(event.dataTransfer.files || []));
    });
    filesEl.addEventListener('change', () => setFiles(Array.from(filesEl.files || [])));

    function setFiles(files) {
      selectedFiles = files.filter(file => file.name.toLowerCase().endsWith('.csv'));
      filelist.innerHTML = selectedFiles.map(file => `<span class="chip">${escapeHtml(file.name)}</span>`).join('');
    }

    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (!selectedFiles.length) {
        statusEl.textContent = 'Choose DIM CSV exports first.';
        return;
      }
      const formData = new FormData(form);
      formData.delete('files');
      formData.delete('audit_profile');
      for (const file of selectedFiles) formData.append('files', file, file.name);
      statusEl.textContent = 'Auditing vault exports...';
      document.getElementById('run').disabled = true;
      try {
        const response = await fetch('/api/audit', { method: 'POST', body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Audit failed.');
        audit = data;
        prepareFilters();
        render();
        resultsEl.classList.remove('hidden');
        statusEl.textContent = auditStatusText();
      } catch (error) {
        statusEl.textContent = error.message;
      } finally {
        document.getElementById('run').disabled = false;
      }
    });

    function prepareFilters() {
      fillSelect(kindEl, 'All gear', unique('kind'));
      fillSelect(bucketEl, 'All buckets', unique('bucket'));
      fillSelect(tagEl, 'All tags', unique('tag').concat(['archive', 'favorite', 'junk', 'keep']));
    }

    function unique(field) {
      return Array.from(new Set(audit.recommendations.map(rec => rec[field]).filter(Boolean))).sort();
    }

    function fillSelect(el, label, values) {
      const uniqueValues = Array.from(new Set(values)).sort();
      el.innerHTML = `<option value="">${label}</option>` + uniqueValues.map(value => `<option>${escapeHtml(value)}</option>`).join('');
    }

    function matches(rec) {
      return matchesGlobalFilters(rec) && matchesQueue(rec) && matchesBucket(rec);
    }

    function matchesGlobalFilters(rec) {
      const query = searchEl.value.trim().toLowerCase();
      if (kindEl.value && rec.kind !== kindEl.value) return false;
      if (tagEl.value && rec.tag !== tagEl.value) return false;
      if (!query) return true;
      return [rec.name, rec.kind, rec.reason, rec.comment, rec.bucket, rec.tag, rec.rank, ...(rec.signals || [])].join(' ').toLowerCase().includes(query);
    }

    function matchesQueue(rec) {
      if (activeQueue === 'needs-review' && rec.bucket !== 'needs-review') return false;
      if (activeQueue === 'cleanup' && !['junk', 'replace-now'].includes(rec.bucket)) return false;
      if (activeQueue === 'duplicates' && !rec.duplicate_group) return false;
      if (activeQueue === 'protect' && rec.bucket !== 'protect') return false;
      return true;
    }

    function matchesBucket(rec) {
      return !bucketEl.value || rec.bucket === bucketEl.value;
    }

    function render() {
      renderQueues();
      renderAuditSummary();
      const visible = audit.recommendations.map((rec, index) => ({rec, index})).filter(({rec}) => matches(rec));
      const bucketCounts = bucketCountsForContext();
      statsEl.innerHTML = bucketCounts.sort((a,b) => b[1] - a[1]).map(([bucket, count]) => `<button class="stat" type="button" data-bucket-filter="${escapeHtml(bucket)}" aria-pressed="${bucketEl.value === bucket}"><strong>${count}</strong><span>${escapeHtml(bucket)}</span></button>`).join('');
      renderProgress(visible.length);
      const dupes = duplicateSummaryForVisible(visible.map(({rec}) => rec));
      document.getElementById('duplicate-summary').textContent = dupes.groups ? `${dupes.groups} duplicate groups · ${dupes.items} duplicate items` : '';
      rowsEl.innerHTML = visible.map(({rec, index}) => `
        <tr data-bucket="${escapeHtml(rec.bucket)}">
          <td><strong>${escapeHtml(rec.name)}</strong><div class="muted">${escapeHtml(rec.kind)} · ${escapeHtml(rec.item_id)}</div></td>
          <td><span class="pill">${escapeHtml(rec.bucket)}</span><div class="muted">${escapeHtml(rec.rank || '')}</div></td>
          <td><select class="tag-edit" data-index="${index}">${['archive','favorite','junk','keep'].map(tag => `<option value="${tag}" ${tag === rec.tag ? 'selected' : ''}>${tag}</option>`).join('')}</select></td>
          <td>${escapeHtml(rec.confidence)}</td>
          <td class="reason">${escapeHtml(rec.reason)}<div class="muted">${escapeHtml((rec.sources || []).join(', '))}</div><div class="signals">${(rec.signals || []).map(signal => `<span class="signal">${escapeHtml(signal)}</span>`).join('')}</div><textarea class="comment-edit" data-index="${index}">${escapeHtml(rec.comment)}</textarea><label style="margin-top: 8px; display: inline-flex; align-items: center; gap: 6px;"><input class="approve-edit" type="checkbox" data-index="${index}" ${rec.approved ? 'checked' : ''}> Approved</label></td>
        </tr>`).join('');
    }

    rowsEl.addEventListener('change', event => {
      if (!audit) return;
      const index = Number(event.target.dataset.index);
      if (!Number.isInteger(index)) return;
      const rec = audit.recommendations[index];
      if (event.target.classList.contains('tag-edit')) {
        rec.tag = event.target.value;
        if (!rec.signals.includes('reviewed-decision')) rec.signals.push('reviewed-decision');
        render();
      }
      if (event.target.classList.contains('approve-edit')) {
        rec.approved = event.target.checked;
        if (rec.approved && !rec.signals.includes('wizard-approved')) rec.signals.push('wizard-approved');
        renderProgress(audit.recommendations.map((item, itemIndex) => ({rec: item, index: itemIndex})).filter(({rec}) => matches(rec)).length);
      }
    });

    rowsEl.addEventListener('input', event => {
      if (!audit || !event.target.classList.contains('comment-edit')) return;
      const index = Number(event.target.dataset.index);
      const rec = audit.recommendations[index];
      rec.comment = event.target.value;
      rec.comment_override = event.target.value;
      if (!rec.signals.includes('reviewed-decision')) rec.signals.push('reviewed-decision');
    });

    statsEl.addEventListener('click', event => {
      const button = event.target.closest('.stat');
      if (!button) return;
      const bucket = button.dataset.bucketFilter || '';
      activeQueue = '';
      bucketEl.value = bucketEl.value === bucket ? '' : bucket;
      render();
    });

    function bucketCountsForContext() {
      const counts = new Map();
      for (const bucket of unique('bucket')) counts.set(bucket, 0);
      for (const rec of audit.recommendations) {
        if (!matchesGlobalFilters(rec) || !matchesQueue(rec)) continue;
        counts.set(rec.bucket, (counts.get(rec.bucket) || 0) + 1);
      }
      return Array.from(counts.entries());
    }

    function duplicateSummaryForVisible(records) {
      const groups = new Set();
      let items = 0;
      for (const rec of records) {
        if (!rec.duplicate_group) continue;
        groups.add(rec.duplicate_group);
        items += 1;
      }
      return {groups: groups.size, items};
    }

    function renderAuditSummary() {
      const preserved = countSignal('returning-guardian:auto-preserve-note', 'armor');
      const review = audit.recommendations.filter(rec => rec.bucket === 'needs-review').length;
      const cleanup = audit.recommendations.filter(rec => ['junk', 'replace-now'].includes(rec.bucket)).length;
      const parts = [];
      if (preserved) parts.push(`${preserved} noted armor pieces auto-preserved`);
      parts.push(`${review} items need review`);
      if (cleanup) parts.push(`${cleanup} cleanup candidates`);
      auditSummaryEl.textContent = parts.join(' · ');
    }

    function auditStatusText() {
      const preserved = countSignal('returning-guardian:auto-preserve-note', 'armor');
      return preserved
        ? `Reviewed ${audit.recommendations.length} items. Auto-preserved ${preserved} noted armor pieces.`
        : `Reviewed ${audit.recommendations.length} items.`;
    }

    function countSignal(signal, kind) {
      return audit.recommendations.filter(rec => (!kind || rec.kind === kind) && (rec.signals || []).includes(signal)).length;
    }

    function renderQueues() {
      const scoped = audit.recommendations.filter(matchesGlobalFilters);
      const queues = [
        ['all', 'All', scoped.length],
        ['needs-review', 'Review', scoped.filter(rec => rec.bucket === 'needs-review').length],
        ['cleanup', 'Cleanup', scoped.filter(rec => ['junk', 'replace-now'].includes(rec.bucket)).length],
        ['duplicates', 'Duplicates', scoped.filter(rec => rec.duplicate_group).length],
        ['protect', 'Protected', scoped.filter(rec => rec.bucket === 'protect').length]
      ];
      queuebarEl.innerHTML = queues.map(([key, label, count]) => `<button class="queue-btn" type="button" data-queue="${key}" aria-pressed="${(activeQueue || 'all') === key}">${escapeHtml(label)} ${count}</button>`).join('');
    }

    queuebarEl.addEventListener('click', event => {
      const button = event.target.closest('.queue-btn');
      if (!button) return;
      const queue = button.dataset.queue;
      activeQueue = queue === 'all' ? '' : queue;
      bucketEl.value = '';
      render();
    });

    function renderProgress(visibleCount) {
      const total = audit.recommendations.length;
      const approved = audit.recommendations.filter(rec => rec.approved).length;
      const remainingReview = audit.recommendations.filter(rec => rec.bucket === 'needs-review' && !rec.approved).length;
      document.getElementById('review-progress').innerHTML = `
        <progress max="${total}" value="${approved}"></progress>
        <span>${approved} approved of ${total}</span>
        <span>${remainingReview} review items remaining</span>
        <span>${visibleCount} visible</span>`;
    }

    for (const el of [searchEl, kindEl, bucketEl, tagEl]) el.addEventListener('input', render);
    document.getElementById('approve-visible').addEventListener('click', () => {
      if (!audit) return;
      for (const rec of audit.recommendations) {
        if (!matches(rec)) continue;
        rec.approved = true;
        if (!rec.signals.includes('wizard-approved')) rec.signals.push('wizard-approved');
      }
      render();
    });
    document.getElementById('export').addEventListener('click', async () => {
      if (!audit) return;
      statusEl.textContent = 'Preparing DIM import CSV...';
      const response = await fetch('/api/export-dim', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({run_id: audit.run_id, recommendations: audit.recommendations})
      });
      if (!response.ok) {
        const data = await response.json();
        statusEl.textContent = data.error || 'Export failed.';
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement('a'), {href: url, download: 'dim-import.csv'});
      a.click();
      URL.revokeObjectURL(url);
      statusEl.textContent = 'DIM import CSV exported.';
    });

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
  </script>
</body>
</html>
"""
