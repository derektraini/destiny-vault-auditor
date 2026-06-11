from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(SRC))

from auditor.destiny_report import load_destiny_report
from auditor.dim_csv import read_csv
from auditor.scoring import AuditConfig, recommend


class AuditorTests(unittest.TestCase):
    def test_scoring_buckets(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_weapons.csv")
        index = load_destiny_report(FIXTURES / "synthetic_destiny_report.json")
        recs = {row["Name"]: recommend(row, index) for row in rows}

        self.assertEqual(recs["Solar Friend"].bucket, "keep")
        self.assertEqual(recs["Solar Friend"].tag, "keep")
        self.assertEqual(recs["Old Rocket"].bucket, "replace-now")
        self.assertEqual(recs["Old Rocket"].tag, "junk")
        self.assertEqual(recs["Crafted Workhorse"].bucket, "protect")
        self.assertEqual(recs["Crafted Workhorse"].tag, "favorite")
        self.assertEqual(recs["PvP Comfort"].bucket, "keep-refarm")
        self.assertEqual(recs["Plain Old Thing"].bucket, "junk")

    def test_cli_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    "--weapons-csv",
                    str(FIXTURES / "synthetic_dim_weapons.csv"),
                    "--destiny-report-json",
                    str(FIXTURES / "synthetic_destiny_report.json"),
                    "--out-dir",
                    str(out_dir),
                    "--cleanup-mode",
                    "aggressive",
                    "--locked-behavior",
                    "protect",
                    "--old-vs-new",
                    "prefer-new",
                    "--low-power-below",
                    "600",
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Reviewed 5 items", result.stdout)
            for name in ["dim-import.csv", "audit-summary.md", "decisions.json", "vault-review.html"]:
                self.assertTrue((out_dir / name).exists(), name)

            with (out_dir / "dim-import.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            by_name = {row["Name"]: row for row in rows}
            self.assertEqual(by_name["Old Rocket"]["Tag"], "junk")
            self.assertIn("DVA: REPLACE-NOW", by_name["Old Rocket"]["Notes"])
            self.assertEqual(by_name["Crafted Workhorse"]["Tag"], "favorite")

            decisions = (out_dir / "decisions.json").read_text(encoding="utf-8")
            self.assertIn('"cleanup_mode": "aggressive"', decisions)
            self.assertIn('"locked_behavior": "protect"', decisions)

    def test_locked_behavior_can_protect_or_review(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_weapons.csv")
        index = load_destiny_report(FIXTURES / "synthetic_destiny_report.json")
        row = rows[-1].copy()
        row["Locked"] = "true"

        protected = recommend(row, index, AuditConfig(locked_behavior="protect"))
        self.assertEqual(protected.bucket, "protect")
        self.assertEqual(protected.rank, "favorite")
        self.assertIn("locked:protect", protected.signals)

        review = recommend(row, index, AuditConfig(locked_behavior="review"))
        self.assertEqual(review.bucket, "needs-review")
        self.assertEqual(review.rank, "review")
        self.assertIn("locked:review", review.signals)


if __name__ == "__main__":
    unittest.main()
