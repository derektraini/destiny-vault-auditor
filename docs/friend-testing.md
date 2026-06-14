# Friend Testing Guide

This is a local, manual DIM metadata helper. It recommends tags and comments; it does not dismantle, move, equip, lock, unlock, or write to DIM automatically.

## What To Export

From DIM, export:

- Weapons CSV.
- Armor CSV.

Save both under `dim-exports/` or name them `*.private.csv`.

## Run

```bash
python3 scripts/destiny-vault-auditor.py start
```

Drop or choose the DIM CSV exports in the browser. The wizard detects weapons and armor automatically.

The advanced CLI still works if you want repeatable automation:

```bash
python3 scripts/destiny-vault-auditor.py ~/Downloads/dim-weapons.csv ~/Downloads/dim-armor.csv \
  --out-dir outputs/my-audit
```

Optional sources:

```bash
mkdir -p source-cache
curl -L "https://docs.google.com/spreadsheets/d/14LnzOhmeXzKaSV3OR35pQJkclg6vLC4YmKtlKTctY3o/export?format=csv&gid=631213508" \
  -o source-cache/armor-set-ratings.csv
```

The wizard uses the cached armor set sheet automatically when it exists. For advanced CLI runs, add:

```bash
--armor-set-ratings-csv source-cache/armor-set-ratings.csv
```

You can also add a local wishlist or triage file:

```bash
--wishlist-source source-cache/wishlist.json
```

Wishlist sources are optional. They are most useful when you already have curated roll notes from DIM, a podcast panel, or a trusted friend and want the auditor to explain that context in the HTML review.

## Review

Start with:

- `junk`
- `replace-now`
- `needs-review`
- duplicate groups

You can edit each row's tag and comment in the browser, then export the final DIM import CSV directly.

## Advanced: Generate Final CSV From Review

If you used the standalone HTML artifact instead of the wizard, export reviewed decisions and rerun:

```bash
python3 scripts/destiny-vault-auditor.py \
  --armor-set-ratings-csv source-cache/armor-set-ratings.csv \
  --review-decisions-json ~/Downloads/decisions.json \
  --out-dir outputs/my-final-audit
```

Use the same optional source files on the final pass that you used on the first pass. Omit any optional source flag if you did not use that file. The wizard handles this internally.

## Import Back Into DIM

Import this file into DIM:

```text
dim-import.csv
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
