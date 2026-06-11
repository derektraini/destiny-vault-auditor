from __future__ import annotations

import argparse
from pathlib import Path

from .destiny_report import load_destiny_report
from .dim_csv import append_audit_note, read_csv, write_csv
from .review_artifact import write_decisions, write_html, write_summary
from .scoring import AuditConfig, recommend


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a DIM weapon CSV and generate review artifacts.")
    parser.add_argument("--weapons-csv", type=Path, required=True, help="DIM weapon CSV export.")
    parser.add_argument("--destiny-report-json", type=Path, help="destiny.report weapon JSON export.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs"), help="Output directory.")
    parser.add_argument("--high-level", type=int, default=30, help="Weapon level above this is protected.")
    parser.add_argument("--invested-level", type=int, default=20, help="Weapon level above this gets investment protection.")
    args = parser.parse_args()

    fields, rows = read_csv(args.weapons_csv)
    destiny_report = load_destiny_report(args.destiny_report_json) if args.destiny_report_json else None
    config = AuditConfig(high_level_threshold=args.high_level, invested_level_threshold=args.invested_level)

    recommendations = [recommend(row, destiny_report, config) for row in rows]
    output_rows = []
    for row, rec in zip(rows, recommendations, strict=True):
        out = row.copy()
        out["Tag"] = rec.tag
        out["Notes"] = append_audit_note(out.get("Notes", ""), rec.comment)
        output_rows.append(out)

    out_dir = args.out_dir
    write_csv(out_dir / "dim-import.csv", fields, output_rows)
    write_summary(out_dir / "audit-summary.md", recommendations)
    write_decisions(out_dir / "decisions.json", recommendations)
    write_html(out_dir / "vault-review.html", recommendations)

    print(f"Reviewed {len(recommendations)} items")
    print(f"Wrote {out_dir / 'dim-import.csv'}")
    print(f"Wrote {out_dir / 'audit-summary.md'}")
    print(f"Wrote {out_dir / 'decisions.json'}")
    print(f"Wrote {out_dir / 'vault-review.html'}")


if __name__ == "__main__":
    main()
