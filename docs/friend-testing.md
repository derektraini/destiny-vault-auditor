# Friend Testing Guide

This is a local, manual DIM metadata helper. It recommends tags and comments; it does not dismantle, move, equip, lock, unlock, or write to DIM automatically.

## What To Export

From DIM, export:

- Weapons CSV.
- Armor CSV.

Save both under `dim-exports/` or name them `*.private.csv`.

## Run

```bash
python3 scripts/destiny-vault-auditor.py \
  --weapons-csv dim-exports/weapons.private.csv \
  --armor-csv dim-exports/armor.private.csv \
  --out-dir outputs/my-audit \
  --cleanup-mode clean-slate \
  --locked-behavior review
```

Optional sources:

```bash
mkdir -p source-cache
curl -L "https://docs.google.com/spreadsheets/d/14LnzOhmeXzKaSV3OR35pQJkclg6vLC4YmKtlKTctY3o/export?format=csv&gid=631213508" \
  -o source-cache/armor-set-ratings.csv
```

Then add:

```bash
--armor-set-ratings-csv source-cache/armor-set-ratings.csv
```

## Review

Open:

```bash
open outputs/my-audit/vault-review.html
```

Start with:

- `junk`
- `replace-now`
- `needs-review`

## Import Back Into DIM

Import this file into DIM:

```text
outputs/my-audit/dim-import.csv
```

It only contains DIM metadata columns:

```text
Name,Hash,Id,Tag,Notes
```

Importing it sends the auditor's proposed tags/comments back to DIM. It still does not dismantle anything.

## Known Limits

- Armor scoring is conservative.
- Duplicate grouping is not fully built yet.
- Reviewed HTML decisions are not consumed back into a second final CSV yet.
- Treat all `junk` as review candidates until you trust the model.
