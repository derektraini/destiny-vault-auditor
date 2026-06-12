---
name: destiny-vault-auditor
description: Run the local Destiny Vault Auditor workflow for DIM weapon and armor CSV exports, optional public source files, HTML review, reviewed decisions JSON, and final DIM metadata CSV generation.
---

# Destiny Vault Auditor

Use this skill when the user wants to audit Destiny 2 gear from local DIM CSV exports, especially for returning-player vault cleanup.

## Safety Contract

- Work only with local files the user provides.
- Do not dismantle, move, equip, lock, unlock, or modify gear directly.
- Do not use DIM Sync writes.
- Do not require Bungie OAuth.
- Do not require browser automation.
- Keep private DIM exports in ignored/private paths such as `dim-exports/` or `*.private.csv`.
- Final DIM import files must contain only `Name`, `Hash`, `Id`, `Tag`, and `Notes`.

## Workflow

1. Confirm the user has exported DIM weapon and/or armor CSVs.
2. Prefer both `--weapons-csv` and `--armor-csv` when available.
3. Add optional local public/source files when present:
   - `--destiny-report-json`
   - `--armor-set-ratings-csv`
   - `--wishlist-source`
4. Run the repo CLI through the plugin wrapper:

```bash
python3 plugin/destiny-vault-auditor/scripts/audit_vault.py \
  --weapons-csv dim-exports/weapons.private.csv \
  --armor-csv dim-exports/armor.private.csv \
  --destiny-report-json source-cache/destiny-report-weapons.json \
  --armor-set-ratings-csv source-cache/armor-set-ratings.csv \
  --wishlist-source source-cache/wishlist.json \
  --out-dir outputs/my-audit
```

5. Tell the user to review `vault-review.html`.
6. If the user exports reviewed decisions JSON from the HTML artifact, run a second pass:

```bash
python3 plugin/destiny-vault-auditor/scripts/audit_vault.py \
  --weapons-csv dim-exports/weapons.private.csv \
  --armor-csv dim-exports/armor.private.csv \
  --destiny-report-json source-cache/destiny-report-weapons.json \
  --armor-set-ratings-csv source-cache/armor-set-ratings.csv \
  --wishlist-source source-cache/wishlist.json \
  --review-decisions-json outputs/my-audit/decisions.json \
  --out-dir outputs/my-final-audit
```

7. Point the user at `dim-import.csv` for manual DIM metadata import.

## Expected Outputs

- `audit-summary.md`
- `vault-review.html`
- `decisions.json`
- `dim-import.csv`
- `dim-import-weapons.csv` and `dim-import-armor.csv` when both inputs are provided

## Verification

For repo changes, run:

```bash
python3 -m py_compile src/auditor/*.py scripts/destiny-vault-auditor.py plugin/destiny-vault-auditor/scripts/audit_vault.py
python3 -m unittest discover -s tests
```

For a smoke test, use the synthetic fixtures and verify the generated `dim-import.csv` header is exactly:

```text
Name,Hash,Id,Tag,Notes
```
