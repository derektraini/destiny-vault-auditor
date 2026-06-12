from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from .destiny_report import load_destiny_report
from .dim_csv import append_audit_note, read_csv, write_csv
from .review_artifact import write_decisions, write_html, write_summary
from .scoring import AuditConfig, recommend


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a DIM weapon CSV and generate review artifacts.")
    parser.add_argument("--weapons-csv", type=Path, required=True, help="DIM weapon CSV export.")
    parser.add_argument("--destiny-report-json", type=Path, help="destiny.report weapon JSON export.")
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

    _validate_input_path(parser, args.weapons_csv, args.allow_unignored_input)
    fields, rows = read_csv(args.weapons_csv)
    _validate_weapon_csv(parser, fields, rows)
    destiny_report = load_destiny_report(args.destiny_report_json) if args.destiny_report_json else None
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

    recommendations = [recommend(row, destiny_report, config) for row in rows]
    output_rows = []
    for row, rec in zip(rows, recommendations, strict=True):
        out = row.copy()
        out["Tag"] = rec.tag
        out["Notes"] = append_audit_note(out.get("Notes", ""), rec.comment)
        output_rows.append(out)

    out_dir = args.out_dir
    write_csv(out_dir / "dim-import.csv", fields, output_rows)
    write_summary(out_dir / "audit-summary.md", recommendations, config)
    write_decisions(out_dir / "decisions.json", recommendations, config)
    write_html(out_dir / "vault-review.html", recommendations, config)

    print(f"Reviewed {len(recommendations)} items")
    print(f"Wrote {out_dir / 'dim-import.csv'}")
    print(f"Wrote {out_dir / 'audit-summary.md'}")
    print(f"Wrote {out_dir / 'decisions.json'}")
    print(f"Wrote {out_dir / 'vault-review.html'}")


def _validate_input_path(parser: argparse.ArgumentParser, path: Path, allow_unignored: bool) -> None:
    if not path.exists():
        parser.error(f"weapons CSV does not exist: {path}")
    if path.suffix.lower() != ".csv":
        parser.error(f"weapons CSV must be a .csv file: {path}")

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
        "weapons CSV is inside the repo but is not ignored by Git. "
        "Move it under dim-exports/, rename it *.private.csv, or pass --allow-unignored-input."
    )


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
