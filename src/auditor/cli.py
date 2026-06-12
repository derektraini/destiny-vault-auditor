from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .armor_analysis import apply_armor_context
from .armor_sets import load_armor_set_ratings
from .destiny_report import load_destiny_report
from .dim_csv import append_audit_note, read_csv, write_csv
from .duplicates import apply_duplicate_grouping
from .review_artifact import write_decisions, write_html, write_summary
from .scoring import AuditConfig, Recommendation, recommend, recommend_armor
from .wishlist import apply_wishlist_matches, load_wishlist


REQUIRED_WEAPON_FIELDS = {
    "Name",
    "Hash",
    "Id",
    "Tag",
    "Rarity",
    "Tier",
    "Power",
    "Crafted",
    "Crafted Level",
    "Season",
    "Notes",
}

REQUIRED_ARMOR_FIELDS = {
    "Name",
    "Hash",
    "Id",
    "Tag",
    "Rarity",
    "Tier",
    "Type",
    "Power",
    "Notes",
}

DIM_IMPORT_FIELDS = ["Name", "Hash", "Id", "Tag", "Notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit DIM weapon and armor CSVs and generate review artifacts.")
    parser.add_argument("--weapons-csv", type=Path, help="DIM weapon CSV export.")
    parser.add_argument("--armor-csv", type=Path, help="DIM armor CSV export.")
    parser.add_argument("--destiny-report-json", type=Path, help="destiny.report weapon JSON export.")
    parser.add_argument("--armor-set-ratings-csv", type=Path, help="Armor set rating sheet CSV export.")
    parser.add_argument("--wishlist-source", type=Path, help="Local wishlist/triage JSON or CSV source.")
    parser.add_argument("--review-decisions-json", type=Path, help="Reviewed decisions JSON exported from vault-review.html.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs"), help="Output directory.")
    parser.add_argument(
        "--cleanup-mode",
        choices=("gentle", "clean-slate", "aggressive"),
        default="clean-slate",
        help="Overall audit posture.",
    )
    parser.add_argument("--high-level", type=int, default=30, help="Weapon level above this is protected.")
    parser.add_argument("--invested-level", type=int, default=20, help="Weapon level above this gets investment protection.")
    parser.add_argument(
        "--locked-behavior",
        choices=("protect", "review", "ignore"),
        default="review",
        help="How locked DIM items affect recommendations.",
    )
    parser.add_argument(
        "--duplicate-pruning",
        choices=("keep-more", "balanced", "prune-hard"),
        default="balanced",
        help="Preference hint for duplicate handling.",
    )
    parser.add_argument(
        "--old-vs-new",
        choices=("keep-bridges", "balanced", "prefer-new"),
        default="balanced",
        help="Preference hint for legacy rolls when newer versions exist.",
    )
    parser.add_argument(
        "--pvp-caution",
        choices=("cautious", "balanced", "strict"),
        default="balanced",
        help="How cautiously to treat PvP notes and feel rolls.",
    )
    parser.add_argument(
        "--low-power-below",
        type=int,
        default=0,
        help="Power at or below this value is noted as low-power evidence. Use 0 to disable.",
    )
    parser.add_argument(
        "--allow-unignored-input",
        action="store_true",
        help="Allow a DIM export inside the repo even if Git does not ignore it.",
    )
    args = parser.parse_args()

    if not args.weapons_csv and not args.armor_csv:
        parser.error("provide --weapons-csv, --armor-csv, or both")

    if args.destiny_report_json:
        _validate_source_path(parser, args.destiny_report_json, "destiny.report JSON", ".json")
    if args.armor_set_ratings_csv:
        _validate_source_path(parser, args.armor_set_ratings_csv, "armor set ratings CSV", ".csv")
    if args.wishlist_source:
        _validate_wishlist_path(parser, args.wishlist_source)
    if args.review_decisions_json:
        _validate_source_path(parser, args.review_decisions_json, "review decisions JSON", ".json")

    destiny_report = load_destiny_report(args.destiny_report_json) if args.destiny_report_json else None
    armor_sets = load_armor_set_ratings(args.armor_set_ratings_csv) if args.armor_set_ratings_csv else None
    wishlist = load_wishlist(args.wishlist_source) if args.wishlist_source else None
    source_labels = _source_labels(args)
    config = AuditConfig(
        cleanup_mode=args.cleanup_mode,
        high_level_threshold=args.high_level,
        invested_level_threshold=args.invested_level,
        locked_behavior=args.locked_behavior,
        duplicate_pruning=args.duplicate_pruning,
        old_vs_new=args.old_vs_new,
        pvp_caution=args.pvp_caution,
        low_power_below=args.low_power_below,
    )

    inputs: list[tuple[str, list[str], list[dict[str, str]], list[Recommendation]]] = []

    if args.weapons_csv:
        _validate_input_path(parser, args.weapons_csv, args.allow_unignored_input, "weapons CSV")
        weapon_fields, weapon_rows = read_csv(args.weapons_csv)
        _validate_weapon_csv(parser, weapon_fields, weapon_rows)
        weapon_recommendations = [recommend(row, destiny_report, config) for row in weapon_rows]
        inputs.append(("weapons", weapon_fields, weapon_rows, weapon_recommendations))

    if args.armor_csv:
        _validate_input_path(parser, args.armor_csv, args.allow_unignored_input, "armor CSV")
        armor_fields, armor_rows = read_csv(args.armor_csv)
        _validate_armor_csv(parser, armor_fields, armor_rows)
        armor_recommendations = [recommend_armor(row, config, armor_sets) for row in armor_rows]
        inputs.append(("armor", armor_fields, armor_rows, armor_recommendations))

    recommendations = [rec for _, _, _, recs in inputs for rec in recs]
    item_recommendations = [(row, rec) for _, _, rows, recs in inputs for row, rec in zip(rows, recs, strict=True)]
    apply_armor_context(item_recommendations, armor_sets)
    wishlist_count = apply_wishlist_matches(
        item_recommendations,
        wishlist,
    )
    if wishlist:
        print(f"Applied {wishlist_count} wishlist/triage matches")
    duplicate_summary = apply_duplicate_grouping(
        item_recommendations,
        config,
    )
    if args.review_decisions_json:
        applied_count, warnings = _apply_review_decisions(args.review_decisions_json, recommendations, parser)
        print(f"Applied {applied_count} reviewed decisions")
        for warning in warnings:
            print(f"WARNING: {warning}", file=sys.stderr)

    out_dir = args.out_dir
    combined_rows: list[dict[str, str]] = []
    for name, _, rows, recs in inputs:
        output_rows = _dim_import_rows(rows, recs)
        combined_rows.extend(output_rows)
        if len(inputs) > 1:
            write_csv(out_dir / f"dim-import-{name}.csv", DIM_IMPORT_FIELDS, output_rows)

    write_csv(out_dir / "dim-import.csv", DIM_IMPORT_FIELDS, combined_rows)
    write_summary(out_dir / "audit-summary.md", recommendations, config, source_labels, duplicate_summary)
    write_decisions(out_dir / "decisions.json", recommendations, config, source_labels)
    write_html(out_dir / "vault-review.html", recommendations, config, source_labels, duplicate_summary)

    print(f"Reviewed {len(recommendations)} items")
    print(f"Wrote {out_dir / 'dim-import.csv'}")
    print(f"Wrote {out_dir / 'audit-summary.md'}")
    print(f"Wrote {out_dir / 'decisions.json'}")
    print(f"Wrote {out_dir / 'vault-review.html'}")


def _dim_import_rows(rows: list[dict[str, str]], recs: list[Recommendation]) -> list[dict[str, str]]:
    output_rows = []
    for row, rec in zip(rows, recs, strict=True):
        out = {
            "Name": row.get("Name", ""),
            "Hash": row.get("Hash", ""),
            "Id": row.get("Id", ""),
            "Tag": rec.tag,
            "Notes": append_audit_note(row.get("Notes", ""), rec.comment),
        }
        output_rows.append(out)
    return output_rows


def _source_labels(args: argparse.Namespace) -> list[str]:
    labels: list[str] = []
    if args.weapons_csv:
        labels.append("DIM weapons CSV")
    if args.armor_csv:
        labels.append("DIM armor CSV")
    if args.destiny_report_json:
        labels.append("destiny.report weapon metadata")
    if args.armor_set_ratings_csv:
        labels.append("armor set rating sheet")
    if args.wishlist_source:
        labels.append("wishlist/triage source")
    if args.review_decisions_json:
        labels.append("reviewed decisions JSON")
    return labels


def _apply_review_decisions(
    path: Path,
    recommendations: list[Recommendation],
    parser: argparse.ArgumentParser,
) -> tuple[int, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        parser.error(f"review decisions JSON is invalid: {error}")

    decisions = payload.get("recommendations")
    if not isinstance(decisions, list):
        parser.error("review decisions JSON must contain a recommendations list")

    by_id = {rec.item_id: rec for rec in recommendations if rec.item_id}
    by_hash: dict[str, Recommendation | None] = {}
    for rec in recommendations:
        if not rec.item_hash:
            continue
        if rec.item_hash in by_hash:
            by_hash[rec.item_hash] = None
        else:
            by_hash[rec.item_hash] = rec

    applied = 0
    warnings: list[str] = []
    valid_tags = {"favorite", "keep", "archive", "junk"}

    for decision in decisions:
        if not isinstance(decision, dict):
            warnings.append("skipped malformed decision entry")
            continue
        item_id = str(decision.get("item_id") or "")
        item_hash = str(decision.get("item_hash") or "")
        rec = by_id.get(item_id)
        if rec is None and item_hash:
            rec = by_hash.get(item_hash)
            if rec is None and item_hash in by_hash:
                warnings.append(f"skipped decision for hash {item_hash}: hash matches multiple current items")
                continue

        label = item_id or item_hash or "<missing id>"
        if rec is None:
            warnings.append(f"skipped stale decision for {label}: item is not in the current export")
            continue

        tag = str(decision.get("tag") or rec.tag).strip()
        if tag not in valid_tags:
            warnings.append(f"skipped invalid tag for {label}: {tag}")
            continue

        comment = str(decision.get("comment") or "").strip()
        if comment:
            rec.comment_override = comment
        rec.tag = tag
        rec.rank = _rank_for_reviewed_decision(rec.bucket, tag)
        if "reviewed-decision" not in rec.signals:
            rec.signals.append("reviewed-decision")
        applied += 1

    return applied, warnings


def _rank_for_reviewed_decision(bucket: str, tag: str) -> str:
    if tag == "favorite":
        return "favorite"
    if tag == "junk":
        return "junk"
    if tag == "archive" or bucket == "needs-review":
        return "review"
    return "keep"


def _validate_input_path(parser: argparse.ArgumentParser, path: Path, allow_unignored: bool, label: str) -> None:
    if not path.exists():
        parser.error(f"{label} does not exist: {path}")
    if path.suffix.lower() != ".csv":
        parser.error(f"{label} must be a .csv file: {path}")

    repo_root = _git_root_for(path.parent)
    if not repo_root:
        return

    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repo_root)
    except ValueError:
        return

    if _is_allowed_repo_fixture(relative) or allow_unignored:
        return

    if _git_ignores(repo_root, relative):
        return

    parser.error(
        f"{label} is inside the repo but is not ignored by Git. "
        "Move it under dim-exports/, rename it *.private.csv, or pass --allow-unignored-input."
    )


def _validate_source_path(parser: argparse.ArgumentParser, path: Path, label: str, suffix: str) -> None:
    if not path.exists():
        parser.error(f"{label} does not exist: {path}")
    if path.suffix.lower() != suffix:
        parser.error(f"{label} must be a {suffix} file: {path}")


def _validate_wishlist_path(parser: argparse.ArgumentParser, path: Path) -> None:
    if not path.exists():
        parser.error(f"wishlist/triage source does not exist: {path}")
    if path.suffix.lower() not in {".json", ".csv"}:
        parser.error(f"wishlist/triage source must be a .json or .csv file: {path}")


def _validate_weapon_csv(parser: argparse.ArgumentParser, fields: list[str], rows: list[dict[str, str]]) -> None:
    if not fields:
        parser.error("weapons CSV has no header row")
    missing = sorted(REQUIRED_WEAPON_FIELDS - set(fields))
    if missing:
        parser.error(f"weapons CSV is missing required DIM columns: {', '.join(missing)}")
    if not any(field.startswith("Perks") for field in fields):
        parser.error("weapons CSV does not include any Perks columns")
    if not rows:
        parser.error("weapons CSV has no item rows")


def _validate_armor_csv(parser: argparse.ArgumentParser, fields: list[str], rows: list[dict[str, str]]) -> None:
    if not fields:
        parser.error("armor CSV has no header row")
    missing = sorted(REQUIRED_ARMOR_FIELDS - set(fields))
    if missing:
        parser.error(f"armor CSV is missing required DIM columns: {', '.join(missing)}")
    if not rows:
        parser.error("armor CSV has no item rows")


def _git_root_for(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def _git_ignores(repo_root: Path, relative: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", str(relative)],
        cwd=repo_root,
        check=False,
    )
    return result.returncode == 0


def _is_allowed_repo_fixture(relative: Path) -> bool:
    return relative.parts[:2] == ("tests", "fixtures")


if __name__ == "__main__":
    main()
