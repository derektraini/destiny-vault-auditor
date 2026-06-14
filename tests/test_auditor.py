from __future__ import annotations

import csv
import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures"
PLUGIN = ROOT / "plugin" / "destiny-vault-auditor"

sys.path.insert(0, str(SRC))

from auditor.armor_analysis import analyze_armor
from auditor.armor_sets import load_armor_set_ratings
from auditor.destiny_report import load_destiny_report
from auditor.dim_csv import read_csv
from auditor.duplicates import apply_duplicate_grouping
from auditor.scoring import AuditConfig, recommend, recommend_armor
from auditor.wizard import create_wizard_server
from auditor.wishlist import load_wishlist


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

    def test_armor_notes_with_strong_legacy_intent_are_auto_preserved(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_armor.csv")
        strong_armor = dict(rows[0])
        strong_armor["Tag"] = "keep"
        strong_armor["Notes"] = "legacy build piece"

        rec = recommend_armor(strong_armor)

        self.assertEqual(rec.bucket, "protect")
        self.assertEqual(rec.tag, "keep")
        self.assertIn("legacy armor note", rec.reason)
        self.assertIn("returning-guardian:auto-preserve-note", rec.signals)

    def test_armor_notes_without_strong_fit_still_need_review(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_armor.csv")
        weak_armor = dict(rows[1])
        weak_armor["Tag"] = "keep"
        weak_armor["Notes"] = "maybe old build piece"

        rec = recommend_armor(weak_armor)

        self.assertEqual(rec.bucket, "needs-review")
        self.assertIn("personal note", rec.reason)

    def test_ignored_armor_notes_do_not_force_review(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_armor.csv")
        weak_armor = dict(rows[1])
        weak_armor["Tag"] = "keep"
        weak_armor["Notes"] = "stale DIM test note"

        rec = recommend_armor(weak_armor, AuditConfig(notes_behavior="ignore"))

        self.assertEqual(rec.bucket, "junk")
        self.assertNotIn("personal note", rec.reason)
        self.assertNotIn("notes", rec.signals)

    def test_ignored_weapon_notes_do_not_force_pvp_review(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_weapons.csv")
        row = dict(rows[-1])
        row["Notes"] = "PVP test note from an old pass"
        row["Perks 1"] = "Incandescent"

        respected = recommend(row, None, AuditConfig())
        ignored = recommend(row, None, AuditConfig(notes_behavior="ignore"))

        self.assertEqual(respected.bucket, "needs-review")
        self.assertIn("personal PvP note", respected.reason)
        self.assertEqual(ignored.bucket, "junk")
        self.assertNotIn("notes", ignored.signals)

    def test_armor_set_ratings_affect_scoring(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_armor.csv")
        ratings = load_armor_set_ratings(FIXTURES / "synthetic_armor_set_ratings.csv")
        recs = {row["Id"]: recommend_armor(row, armor_sets=ratings) for row in rows}

        self.assertEqual(recs["armor-1"].bucket, "keep")
        self.assertIn("set-rating:S", recs["armor-1"].signals)
        self.assertIn("armor-role:survival", recs["armor-1"].signals)
        self.assertIn("strong stat fit", recs["armor-1"].reason)
        self.assertEqual(recs["armor-2"].bucket, "junk")
        self.assertIn("set-rating:E", recs["armor-2"].signals)
        self.assertIn("weak stat fit", recs["armor-2"].reason)
        self.assertEqual(recs["armor-4"].bucket, "needs-review")
        self.assertIn("useful Dark Age", recs["armor-4"].reason)
        self.assertIn("weak stat fit", recs["armor-4"].reason)

    def test_armor_profile_parses_archetype_class_and_role(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_armor.csv")
        by_id = {row["Id"]: row for row in rows}

        support = analyze_armor(by_id["armor-1"])
        old_boots = analyze_armor(by_id["armor-2"])

        self.assertEqual(support.armor_class, "Titan")
        self.assertEqual(support.archetype, "Survival")
        self.assertEqual(support.role, "survival")
        self.assertEqual(support.stat_fit, "strong stat fit")
        self.assertEqual(old_boots.role, "weapon-stat")
        self.assertEqual(old_boots.stat_fit, "weak stat fit")

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
            self.assertIn("only copy of a useful set/slot", summary)

            for name in ["dim-import.csv", "dim-import-weapons.csv", "dim-import-armor.csv"]:
                with (out_dir / name).open(newline="", encoding="utf-8") as handle:
                    self.assertEqual(csv.DictReader(handle).fieldnames, ["Name", "Hash", "Id", "Tag", "Notes"])

    def test_cli_autodetects_dragged_dim_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    str(FIXTURES / "synthetic_dim_weapons.csv"),
                    str(FIXTURES / "synthetic_dim_armor.csv"),
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
            self.assertTrue((out_dir / "dim-import-weapons.csv").exists())
            self.assertTrue((out_dir / "dim-import-armor.csv").exists())

    def test_cli_discovers_default_dim_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            export_dir = tmp_path / "dim-exports"
            export_dir.mkdir()
            (export_dir / "weapons.private.csv").write_text(
                (FIXTURES / "synthetic_dim_weapons.csv").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (export_dir / "armor.private.csv").write_text(
                (FIXTURES / "synthetic_dim_armor.csv").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "auditor.cli",
                    "--out-dir",
                    str(tmp_path / "out"),
                ],
                cwd=tmp_path,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Reviewed 12 items", result.stdout)
            self.assertTrue((tmp_path / "out" / "dim-import.csv").exists())

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
            self.assertIn("only-copy-useful-set-slot", by_id["armor-4"]["signals"])
            armor_group = [by_id["armor-2"], by_id["armor-6"]]
            self.assertTrue(any(rec["tag"] != "junk" for rec in armor_group))
            self.assertTrue(all(rec["duplicate_group"] for rec in armor_group))

            html = (out_dir / "vault-review.html").read_text(encoding="utf-8")
            self.assertIn("Duplicate Queue", html)
            self.assertIn("duplicateSummary", html)

    def test_ignored_notes_do_not_protect_duplicate_copies(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_weapons.csv")
        best_row = dict(rows[-1])
        copy_row = dict(rows[-1])
        best_row["Id"] = "best-copy"
        best_row["Notes"] = ""
        copy_row["Id"] = "noted-copy"
        copy_row["Notes"] = "stale duplicate note"
        best_rec = recommend(best_row, None)
        copy_rec = recommend(copy_row, None)
        best_rec.bucket = "protect"
        best_rec.tag = "favorite"
        copy_rec.bucket = "keep"
        copy_rec.tag = "keep"

        apply_duplicate_grouping(
            [(best_row, best_rec), (copy_row, copy_rec)],
            AuditConfig(duplicate_pruning="prune-hard", notes_behavior="respect"),
        )
        self.assertEqual(copy_rec.bucket, "keep")

        best_rec = recommend(best_row, None)
        copy_rec = recommend(copy_row, None, AuditConfig(notes_behavior="ignore"))
        best_rec.bucket = "protect"
        best_rec.tag = "favorite"
        copy_rec.bucket = "keep"
        copy_rec.tag = "keep"
        apply_duplicate_grouping(
            [(best_row, best_rec), (copy_row, copy_rec)],
            AuditConfig(duplicate_pruning="prune-hard", notes_behavior="ignore"),
        )
        self.assertEqual(copy_rec.bucket, "junk")

    def test_wishlist_loader_supports_json_and_csv(self) -> None:
        _, rows = read_csv(FIXTURES / "synthetic_dim_weapons.csv")
        by_id = {row["Id"]: row for row in rows}
        index = load_wishlist(FIXTURES / "synthetic_wishlist.json")

        exact = index.match(by_id["item-2"])
        partial = index.match(by_id["item-5"])

        self.assertIsNotNone(exact)
        self.assertEqual(exact.strength, "exact")
        self.assertEqual(exact.entry.role, "legacy boss DPS bridge")
        self.assertIsNotNone(partial)
        self.assertEqual(partial.strength, "partial")
        self.assertTrue(partial.stale)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "wishlist.csv"
            csv_path.write_text(
                "name,role,recommended_combos,source_name,source_date\n"
                "Old Rocket,spreadsheet DPS,Impulse Amplifier+Cluster Bomb,CSV Test,2026-06-01\n",
                encoding="utf-8",
            )
            csv_index = load_wishlist(csv_path)
            csv_match = csv_index.match(by_id["item-2"])

        self.assertIsNotNone(csv_match)
        self.assertEqual(csv_match.strength, "exact")
        self.assertEqual(csv_match.entry.source_name, "CSV Test")

    def test_cli_applies_wishlist_source_to_weapon_recommendations(self) -> None:
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
                    "--wishlist-source",
                    str(FIXTURES / "synthetic_wishlist.json"),
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": str(SRC)},
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn("Applied 2 wishlist/triage matches", result.stdout)
            decisions = json.loads((out_dir / "decisions.json").read_text(encoding="utf-8"))
            by_id = {rec["item_id"]: rec for rec in decisions["recommendations"]}
            self.assertEqual(by_id["item-2"]["bucket"], "keep")
            self.assertEqual(by_id["item-2"]["tag"], "keep")
            self.assertIn("wishlist-match", by_id["item-2"]["signals"])
            self.assertIn("legacy boss DPS bridge", by_id["item-2"]["reason"])
            self.assertEqual(by_id["item-5"]["bucket"], "needs-review")
            self.assertEqual(by_id["item-5"]["tag"], "archive")
            self.assertIn("wishlist-partial", by_id["item-5"]["signals"])
            self.assertIn("wishlist-stale", by_id["item-5"]["signals"])
            self.assertIn("wishlist/triage source", decisions["sources"])

            with (out_dir / "dim-import.csv").open(newline="", encoding="utf-8") as handle:
                rows = {row["Id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["item-2"]["Tag"], "keep")
            self.assertIn("curated wishlist match", rows["item-2"]["Notes"])
            self.assertNotIn(".. Sources:", rows["item-2"]["Notes"])
            self.assertEqual(rows["item-5"]["Tag"], "archive")
            self.assertIn("source is older", rows["item-5"]["Notes"])

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

    def test_cli_explains_documentation_placeholder_paths(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "auditor.cli",
                "--weapons-csv",
                str(FIXTURES / "synthetic_dim_weapons.csv"),
                "--destiny-report-json",
                "path/to/destiny-report-weapons.json",
            ],
            cwd=ROOT,
            env={"PYTHONPATH": str(SRC)},
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("omit --destiny-report-json", result.stderr)
        self.assertIn("documentation placeholder", result.stderr)

    def test_no_install_wrapper_shows_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/destiny-vault-auditor.py", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("Audit DIM weapon and armor CSVs", result.stdout)
        self.assertIn("start", result.stdout)

    def test_start_subcommand_shows_wizard_help(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/destiny-vault-auditor.py", "start", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("Start the local Destiny Vault Auditor wizard", result.stdout)
        self.assertIn("--no-open", result.stdout)

    def test_wizard_audits_uploads_and_exports_dim_csv(self) -> None:
        server = create_wizard_server("127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            status, source_payload, _ = _request(host, port, "GET", "/api/sources", b"", {})
            self.assertEqual(status, 200, source_payload.decode("utf-8"))
            source_states = json.loads(source_payload.decode("utf-8"))["sources"]
            self.assertTrue(any(source["label"] == "armor set rating sheet" for source in source_states))
            self.assertTrue(all(source["status"] in {"cached", "unavailable"} for source in source_states))

            status, favicon_payload, _ = _request(host, port, "GET", "/favicon.ico", b"", {})
            self.assertEqual(status, 204, favicon_payload.decode("utf-8"))

            status, html_payload, _ = _request(host, port, "GET", "/", b"", {})
            self.assertEqual(status, 200, html_payload.decode("utf-8"))
            html = html_payload.decode("utf-8")
            self.assertIn("Approve visible", html)
            self.assertIn("Refresh sources", html)
            self.assertIn("Audit style", html)
            self.assertIn("Returning Guardian", html)
            self.assertIn("Use existing DIM notes as intent", html)
            self.assertIn("notes_behavior", html)
            self.assertIn("Advanced rules", html)
            self.assertIn("presetRules", html)
            self.assertIn("review-progress", html)
            self.assertIn("audit-summary", html)
            self.assertIn("data-bucket-filter", html)
            self.assertIn("bucketCountsForContext", html)
            self.assertIn("duplicateSummaryForVisible", html)
            self.assertIn("matchesGlobalFilters", html)
            self.assertIn("queuebar", html)
            self.assertIn("cached", html)

            status, payload, _ = _post_multipart(
                host,
                port,
                "/api/audit",
                {
                    "cleanup_mode": "clean-slate",
                    "locked_behavior": "review",
                    "duplicate_pruning": "balanced",
                    "old_vs_new": "balanced",
                    "pvp_caution": "balanced",
                    "notes_behavior": "ignore",
                },
                [
                    ("files", "synthetic_dim_weapons.csv", (FIXTURES / "synthetic_dim_weapons.csv").read_bytes()),
                    ("files", "synthetic_dim_armor.csv", (FIXTURES / "synthetic_dim_armor.csv").read_bytes()),
                ],
            )
            self.assertEqual(status, 200, payload.decode("utf-8"))
            audit = json.loads(payload.decode("utf-8"))
            self.assertEqual(len(audit["recommendations"]), 12)
            self.assertEqual(audit["config"]["notes_behavior"], "ignore")
            self.assertIn("DIM weapons CSV", audit["sources"])
            self.assertIn("DIM armor CSV", audit["sources"])

            for rec in audit["recommendations"]:
                if rec["item_id"] == "item-2":
                    rec["tag"] = "keep"
                    rec["comment"] = "Manual wizard review: keep this one."
                    rec["approved"] = True
                    break

            status, csv_payload, headers = _post_json(
                host,
                port,
                "/api/export-dim",
                {"run_id": audit["run_id"], "recommendations": audit["recommendations"]},
            )
            self.assertEqual(status, 200, csv_payload.decode("utf-8"))
            self.assertEqual(headers.get("content-type"), "text/csv; charset=utf-8")
            rows = {
                row["Id"]: row
                for row in csv.DictReader(csv_payload.decode("utf-8").splitlines())
            }
            self.assertEqual(rows["item-2"]["Tag"], "keep")
            self.assertEqual(rows["item-2"]["Notes"], "Manual wizard review: keep this one.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_plugin_scaffold_wraps_local_cli(self) -> None:
        manifest_path = PLUGIN / ".codex-plugin" / "plugin.json"
        skill_path = PLUGIN / "skills" / "destiny-vault-auditor" / "SKILL.md"
        wrapper_path = PLUGIN / "scripts" / "audit_vault.py"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "destiny-vault-auditor")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertIn("defaultPrompt", manifest["interface"])
        self.assertTrue(skill_path.exists())
        self.assertIn("Do not use DIM Sync writes", skill_path.read_text(encoding="utf-8"))

        result = subprocess.run(
            [sys.executable, str(wrapper_path), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("Audit DIM weapon and armor CSVs", result.stdout)
        self.assertIn("--wishlist-source", result.stdout)


def _post_multipart(
    host: str,
    port: int,
    path: str,
    fields: dict[str, str],
    files: list[tuple[str, str, bytes]],
) -> tuple[int, bytes, dict[str, str]]:
    boundary = "----dva-test-boundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, filename, payload in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"),
                b"Content-Type: text/csv\r\n\r\n",
                payload,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return _request(
        host,
        port,
        "POST",
        path,
        b"".join(chunks),
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def _post_json(host: str, port: int, path: str, payload: dict[str, object]) -> tuple[int, bytes, dict[str, str]]:
    return _request(
        host,
        port,
        "POST",
        path,
        json.dumps(payload).encode("utf-8"),
        {"Content-Type": "application/json"},
    )


def _request(
    host: str,
    port: int,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
) -> tuple[int, bytes, dict[str, str]]:
    connection = http.client.HTTPConnection(host, port, timeout=20)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        return response.status, payload, {key.lower(): value for key, value in response.getheaders()}
    finally:
        connection.close()


if __name__ == "__main__":
    unittest.main()
