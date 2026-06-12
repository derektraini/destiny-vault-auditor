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

You can also add a local wishlist or triage file:

```bash
--wishlist-source source-cache/wishlist.json
```

Wishlist sources are optional. They are most useful when you already have curated roll notes from DIM, a podcast panel, or a trusted friend and want the auditor to explain that context in the HTML review.

## Review

Open:

```bash
open outputs/my-audit/vault-review.html
```

Start with:

- `junk`
- `replace-now`
- `needs-review`
- the Duplicate Queue near the top of the HTML artifact

You can edit each row's tag and comment in the HTML artifact, then use the export button to save reviewed decisions JSON.

## Generate Final CSV From Review

After exporting reviewed decisions, rerun:

```bash
python3 scripts/destiny-vault-auditor.py \
  --weapons-csv dim-exports/weapons.private.csv \
  --armor-csv dim-exports/armor.private.csv \
  --wishlist-source source-cache/wishlist.json \
  --review-decisions-json path/to/reviewed-decisions.json \
  --out-dir outputs/my-final-audit
```

## Import Back Into DIM

Import this file into DIM:

```text
outputs/my-final-audit/dim-import.csv
```

It only contains DIM metadata columns:

```text
Name,Hash,Id,Tag,Notes
```

Importing it sends the auditor's proposed tags/comments back to DIM. It still does not dismantle anything.

## Known Limits

- Armor scoring is conservative, but now includes set ratings, stat fit, archetype/build-role signals, and only-copy set/slot context.
- Duplicate grouping keeps a best copy visible and marks weaker copies for review/cleanup.
- Wishlist matches are evidence, not final authority; stale and partial matches should still be reviewed.
- Treat all `junk` as review candidates until you trust the model.
