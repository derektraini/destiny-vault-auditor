from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


AUDIT_STAMPS = ("DVA:", "Clean-slate 2026-06-10:", "DR 2026-06-10:")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def perk_names(row: dict[str, str]) -> list[str]:
    perks: list[str] = []
    for key, value in row.items():
        if not key.startswith("Perks"):
            continue
        cleaned = (value or "").replace("*", "").strip()
        if cleaned:
            perks.append(cleaned)
    return perks


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field) or default)
    except ValueError:
        return default


def is_crafted(row: dict[str, str]) -> bool:
    return row.get("Crafted") == "crafted"


def strip_audit_notes(note: str) -> str:
    parts = [part.strip() for part in (note or "").split(" | ") if part.strip()]
    kept = []
    for part in parts:
        if any(part.startswith(stamp) or stamp in part for stamp in AUDIT_STAMPS):
            continue
        kept.append(part)
    return " | ".join(kept)


def append_audit_note(existing: str, audit_note: str) -> str:
    base = strip_audit_notes(existing)
    return f"{base} | {audit_note}" if base else audit_note
