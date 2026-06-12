from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .armor_sets import load_armor_set_ratings
from .destiny_report import load_destiny_report
from .dim_csv import append_audit_note, read_csv, write_csv
from .review_artifact import write_decisions, write_html, write_summary
from .scoring import AuditConfig, Recommendation, recommend, recommend_armor


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit DIM weapon and armor CSVs and generate review artifacts.")
    parser.add_argument("--weapons-csv", type=Path, help="DIM weapon CSV export.")
    parser.add_argument("--armor-csv", type=Path, help="DIM armor CSV export.")
    parser.add_argument("--destiny-report-json", type=Path, help="destiny.report weapon JSON export.")
    parser.add_argument("--armor-set-ratings-csv", type=Path, help="Armor set rating sheet CSV export.")
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

    destiny_report = load_destiny_report(args.destiny_report_json) if args.destiny_report_json else None
    armor_sets = load_armor_set_ratings(args.armor_set_ratings_csv) if args.armor_set_ratings_csv else None
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

    out_dir = args.out_dir
    combined_fields = _combined_fields([fields for _, fields, _, _ in inputs])
    combined_rows: list[dict[str, str]] = []
    for name, fields, rows, recs in inputs:
        output_rows = _apply_recommendations(rows, recs)
        combined_rows.extend(output_rows)
        if len(inputs) > 1:
            write_csv(out_dir / f"dim-import-{name}.csv", fields, output_rows)

    write_csv(out_dir / "dim-import.csv", combined_fields, combined_rows)
    write_summary(out_dir / "audit-summary.md", recommendations, config)
    write_decisions(out_dir / "decisions.json", recommendations, config)
    write_html(out_dir / "vault-review.html", recommendations, config)

    print(f"Reviewed {len(recommendations)} items")
    print(f"Wrote {out_dir / 'dim-import.csv'}")
    print(f"Wrote {out_dir / 'audit-summary.md'}")
    print(f"Wrote {out_dir / 'decisions.json'}")
    print(f"Wrote {out_dir / 'vault-review.html'}")


def _apply_recommendations(rows: list[dict[str, str]], recs: list[Recommendation]) -> list[dict[str, str]]:
    output_rows = []
    for row, rec in zip(rows, recs, strict=True):
        out = row.copy()
        out["Tag"] = rec.tag
        out["Notes"] = append_audit_note(out.get("Notes", ""), rec.comment)
        output_rows.append(out)
    return output_rows


def _combined_fields(field_lists: list[list[str]]) -> list[str]:
    preferred = ["Name", "Hash", "Id", "Tag", "Notes"]
    fields: list[str] = [field for field in preferred if any(field in field_list for field_list in field_lists)]
    for field_list in field_lists:
        for field in field_list:
            if field not in fields:
                fields.append(field)
    return fields


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
