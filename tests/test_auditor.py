from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures"

sys.path.insert(0, str(SRC))

from auditor.armor_sets import load_armor_set_ratings
from auditor.destiny_report import load_destiny_report
from auditor.dim_csv import read_csv
from auditor.scoring import AuditConfig, recommend, recommend_armor


class AuditorTests(unittest.TestCase):
    def test_scoring_buckets(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_weapons.csv")
        index = load_destiny_report(FIXTURES / "synthetic_destiny_report.json")
        recs = {row["Id"]: recommend(row, index) for row in rows}

        self.assertEqual(recs["item-1"].bucket, "keep")
        self.assertEqual(recs["item-1"].tag, "keep")
        self.assertEqual(recs["item-2"].bucket, "replace-now")
        self.assertEqual(recs["item-2"].tag, "junk")
        self.assertEqual(recs["item-3"].bucket, "protect")
        self.assertEqual(recs["item-3"].tag, "favorite")
        self.assertEqual(recs["item-4"].bucket, "keep-refarm")
        self.assertEqual(recs["item-5"].bucket, "junk")

    def test_armor_scoring_buckets(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_armor.csv")
        recs = {row["Id"]: recommend_armor(row) for row in rows}

        self.assertEqual(recs["armor-1"].kind, "armor")
        self.assertEqual(recs["armor-1"].bucket, "keep")
        self.assertEqual(recs["armor-2"].bucket, "junk")
        self.assertEqual(recs["armor-3"].bucket, "protect")
        self.assertEqual(recs["armor-4"].bucket, "needs-review")
        self.assertEqual(recs["armor-5"].bucket, "needs-review")

    def test_armor_set_ratings_affect_scoring(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_armor.csv")
        ratings = load_armor_set_ratings(FIXTURES / "synthetic_armor_set_ratings.csv")
        recs = {row["Id"]: recommend_armor(row, armor_sets=ratings) for row in rows}

        self.assertEqual(recs["armor-1"].bucket, "keep")
        self.assertIn("set-rating:S", recs["armor-1"].signals)
        self.assertEqual(recs["armor-2"].bucket, "junk")
        self.assertIn("set-rating:E", recs["armor-2"].signals)

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

            self.assertIn("Reviewed 6 items", result.stdout)
            for name in ["dim-import.csv", "audit-summary.md", "decisions.json", "vault-review.html"]:
                self.assertTrue((out_dir / name).exists(), name)

            with (out_dir / "dim-import.csv").open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, ["Name", "Hash", "Id", "Tag", "Notes"])
                rows = list(reader)
            by_name = {row["Name"]: row for row in rows}
            self.assertEqual(by_name["Old Rocket"]["Tag"], "junk")
            self.assertIn("DVA: REPLACE-NOW", by_name["Old Rocket"]["Notes"])
            self.assertEqual(by_name["Crafted Workhorse"]["Tag"], "favorite")

            decisions = (out_dir / "decisions.json").read_text(encoding="utf-8")
            self.assertIn('"cleanup_mode": "aggressive"', decisions)
            self.assertIn('"locked_behavior": "protect"', decisions)

    def test_cli_writes_mixed_weapon_and_armor_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    "--weapons-csv",
                    str(FIXTURES / "synthetic_dim_weapons.csv"),
                    "--armor-csv",
                    str(FIXTURES / "synthetic_dim_armor.csv"),
                    "--armor-set-ratings-csv",
                    str(FIXTURES / "synthetic_armor_set_ratings.csv"),
                    "--destiny-report-json",
                    str(FIXTURES / "synthetic_destiny_report.json"),
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Reviewed 12 items", result.stdout)
            for name in [
                "dim-import.csv",
                "dim-import-weapons.csv",
                "dim-import-armor.csv",
                "audit-summary.md",
                "decisions.json",
                "vault-review.html",
            ]:
                self.assertTrue((out_dir / name).exists(), name)

            decisions = (out_dir / "decisions.json").read_text(encoding="utf-8")
            self.assertIn('"kind": "weapon"', decisions)
            self.assertIn('"kind": "armor"', decisions)
            self.assertIn('"armor set ratings"', decisions)
            self.assertIn('"DIM weapons CSV"', decisions)
            self.assertIn('"DIM armor CSV"', decisions)
            self.assertIn('"destiny.report weapon metadata"', decisions)
            self.assertIn('"armor set rating sheet"', decisions)
            summary = (out_dir / "audit-summary.md").read_text(encoding="utf-8")
            self.assertIn("Item kinds: armor 6, weapon 6", summary)
            self.assertIn("## Source Inputs", summary)
            self.assertIn("armor set rating sheet", summary)

            for name in ["dim-import.csv", "dim-import-weapons.csv", "dim-import-armor.csv"]:
                with (out_dir / name).open(newline="", encoding="utf-8") as handle:
                    self.assertEqual(csv.DictReader(handle).fieldnames, ["Name", "Hash", "Id", "Tag", "Notes"])

    def test_cli_reports_duplicate_groups_and_preserves_one_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    "--weapons-csv",
                    str(FIXTURES / "synthetic_dim_weapons.csv"),
                    "--armor-csv",
                    str(FIXTURES / "synthetic_dim_armor.csv"),
                    "--armor-set-ratings-csv",
                    str(FIXTURES / "synthetic_armor_set_ratings.csv"),
                    "--destiny-report-json",
                    str(FIXTURES / "synthetic_destiny_report.json"),
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=True,
            )

            summary = (out_dir / "audit-summary.md").read_text(encoding="utf-8")
            self.assertIn("## Duplicate Groups", summary)
            self.assertIn("- Groups: 2", summary)
            self.assertIn("- Weapon groups: 1", summary)
            self.assertIn("- Armor groups: 1", summary)

            decisions = json.loads((out_dir / "decisions.json").read_text(encoding="utf-8"))
            by_id = {rec["item_id"]: rec for rec in decisions["recommendations"]}
            self.assertEqual(by_id["item-1"]["duplicate_role"], "best")
            self.assertEqual(by_id["item-6"]["duplicate_role"], "copy")
            self.assertIn("duplicate-copy", by_id["item-6"]["signals"])
            armor_group = [by_id["armor-2"], by_id["armor-6"]]
            self.assertTrue(any(rec["tag"] != "junk" for rec in armor_group))
            self.assertTrue(all(rec["duplicate_group"] for rec in armor_group))

            html = (out_dir / "vault-review.html").read_text(encoding="utf-8")
            self.assertIn("Duplicate Queue", html)
            self.assertIn("duplicateSummary", html)

    def test_cli_applies_reviewed_decisions_to_final_dim_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            review_path = Path(tmp) / "reviewed.json"
            review_path.write_text(
                json.dumps(
                    {
                        "schema": "destiny-vault-auditor.review.v1",
                        "recommendations": [
                            {
                                "item_id": "item-2",
                                "tag": "keep",
                                "comment": "Manual review: keep this rocket for nostalgia.",
                            },
                            {
                                "item_hash": "5001",
                                "tag": "archive",
                                "comment": "Manual review: archive this scout.",
                            },
                            {
                                "item_id": "missing-item",
                                "tag": "junk",
                                "comment": "This should warn because it is stale.",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    "--weapons-csv",
                    str(FIXTURES / "synthetic_dim_weapons.csv"),
                    "--armor-csv",
                    str(FIXTURES / "synthetic_dim_armor.csv"),
                    "--destiny-report-json",
                    str(FIXTURES / "synthetic_destiny_report.json"),
                    "--armor-set-ratings-csv",
                    str(FIXTURES / "synthetic_armor_set_ratings.csv"),
                    "--review-decisions-json",
                    str(review_path),
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Applied 2 reviewed decisions", result.stdout)
            self.assertIn("skipped stale decision for missing-item", result.stderr)
            with (out_dir / "dim-import.csv").open(newline="", encoding="utf-8") as handle:
                rows = {row["Id"]: row for row in csv.DictReader(handle)}

            self.assertEqual(rows["item-2"]["Tag"], "keep")
            self.assertEqual(rows["item-2"]["Notes"], "Manual review: keep this rocket for nostalgia.")
            self.assertEqual(rows["item-5"]["Tag"], "archive")
            self.assertEqual(rows["item-5"]["Notes"], "Manual review: archive this scout.")

            decisions = json.loads((out_dir / "decisions.json").read_text(encoding="utf-8"))
            item_2 = next(rec for rec in decisions["recommendations"] if rec["item_id"] == "item-2")
            item_5 = next(rec for rec in decisions["recommendations"] if rec["item_id"] == "item-5")
            self.assertIn("reviewed-decision", item_2["signals"])
            self.assertEqual(item_5["rank"], "review")
            self.assertIn("reviewed decisions JSON", decisions["sources"])

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

    def test_cli_rejects_missing_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad_csv = Path(tmp) / "bad.csv"
            bad_csv.write_text("Name,Id\nAlmost Item,item-1\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    "--weapons-csv",
                    str(bad_csv),
                    "--out-dir",
                    str(Path(tmp) / "out"),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing required DIM columns", result.stderr)

    def test_cli_rejects_unignored_repo_csv(self) -> None:
        unsafe_csv = ROOT / "unsafe_dim_export_for_test.csv"
        unsafe_csv.write_text((FIXTURES / "synthetic_dim_weapons.csv").read_text(encoding="utf-8"), encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    "--weapons-csv",
                    str(unsafe_csv),
                    "--out-dir",
                    str(ROOT / "outputs" / "unsafe-test"),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=False,
            )
        finally:
            unsafe_csv.unlink(missing_ok=True)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the repo but is not ignored by Git", result.stderr)

    def test_no_install_wrapper_shows_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/destiny-vault-auditor.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("Audit DIM weapon and armor CSVs", result.stdout)


if __name__ == "__main__":
    unittest.main()
