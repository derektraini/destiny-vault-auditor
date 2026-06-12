# Destiny Vault Auditor

A local-first Destiny 2 vault auditing companion for Codex.

It reads DIM weapon/armor exports, scores gear with source-backed rules, and generates review artifacts plus a DIM import CSV. It is especially useful for returning players with old vaults who need help deciding what is still worth keeping. It never dismantles, equips, transfers, locks, unlocks, writes to DIM Sync, or uploads vault data.

## Status

Works today:

- DIM weapons and armor CSV parsing.
- Optional destiny.report weapon JSON input.
- Optional armor set rating CSV input.
- Weapon roll scoring with keep/junk/refarm/protect buckets.
- Conservative armor scoring for exotics, locked items, notes, investment, class items, and stat profiles.
- Light audit config for cleanup posture.
- Output files: `dim-import.csv`, `audit-summary.md`, `decisions.json`, `vault-review.html`.

Planned:

- Deeper Armor 3.0 archetype/build scoring.
- Duplicate grouping.
- Wishlist/triage source ingestion.
- Codex plugin packaging.
- Import reviewed HTML decisions back into final CSV generation.

## Setup

Requirements:

- Python 3.10+.
- Git.
- No install or Python packages are required for the current prototype.

Clone and enter the repo:

```bash
git clone https://github.com/derektraini/destiny-vault-auditor.git
cd destiny-vault-auditor
```

Verify the CLI works:

```bash
python3 scripts/destiny-vault-auditor.py --help
python3 -m unittest discover -s tests
```

## Quick Start

Run the synthetic fixture audit:

```bash
python3 scripts/destiny-vault-auditor.py \
  --weapons-csv tests/fixtures/synthetic_dim_weapons.csv \
  --armor-csv tests/fixtures/synthetic_dim_armor.csv \
  --destiny-report-json tests/fixtures/synthetic_destiny_report.json \
  --armor-set-ratings-csv tests/fixtures/synthetic_armor_set_ratings.csv \
  --out-dir outputs/demo
```

Open the review artifact:

```bash
open outputs/demo/vault-review.html
```

## Real DIM Export

Export weapons and armor from DIM and put the CSVs in an ignored/private path such as `dim-exports/`.

```bash
mkdir -p dim-exports
```

The CLI refuses unignored CSV inputs inside the repo by default. Files under `dim-exports/` and `*.private.csv` are ignored by Git.

Optional armor set source:

```bash
mkdir -p source-cache
curl -L "https://docs.google.com/spreadsheets/d/14LnzOhmeXzKaSV3OR35pQJkclg6vLC4YmKtlKTctY3o/export?format=csv&gid=631213508" \
  -o source-cache/armor-set-ratings.csv
```

Run an audit:

```bash
python3 scripts/destiny-vault-auditor.py \
  --weapons-csv dim-exports/weapons.private.csv \
  --armor-csv dim-exports/armor.private.csv \
  --destiny-report-json path/to/destiny-report-weapons.json \
  --armor-set-ratings-csv source-cache/armor-set-ratings.csv \
  --out-dir outputs/my-audit \
  --cleanup-mode clean-slate \
  --locked-behavior review \
  --duplicate-pruning balanced \
  --old-vs-new balanced \
  --pvp-caution balanced
```

Without destiny.report data:

```bash
python3 scripts/destiny-vault-auditor.py \
  --weapons-csv dim-exports/weapons.private.csv \
  --armor-csv dim-exports/armor.private.csv \
  --out-dir outputs/my-audit
```

Review `outputs/my-audit/vault-review.html` before importing `outputs/my-audit/dim-import.csv` into DIM.

## Returning Player Flow

1. Export both weapons and armor from DIM.
2. Add optional sources when available: destiny.report weapon metadata and the armor set rating sheet.
3. Run in `clean-slate` mode with `--locked-behavior review`.
4. In the HTML artifact, start with `junk`, `replace-now`, and `needs-review`.
5. Import the DIM CSV only after the recommendations make sense.

The tool ranks and categorizes gear using vault facts, current-ish source metadata, perk/set heuristics, and personal-intent signals like locks, notes, crafted state, and weapon level.

## Config

- `--weapons-csv`: DIM weapons CSV export.
- `--armor-csv`: DIM armor CSV export.
- `--destiny-report-json`: optional destiny.report weapon JSON export.
- `--armor-set-ratings-csv`: optional armor set bonus rating sheet CSV.
- `--cleanup-mode`: `gentle`, `clean-slate`, `aggressive`.
- `--high-level`: weapon level above this is protected. Default: `30`.
- `--invested-level`: weapon level above this gets investment context. Default: `20`.
- `--locked-behavior`: `protect`, `review`, `ignore`.
- `--duplicate-pruning`: `keep-more`, `balanced`, `prune-hard`.
- `--old-vs-new`: `keep-bridges`, `balanced`, `prefer-new`.
- `--pvp-caution`: `cautious`, `balanced`, `strict`.
- `--low-power-below`: note low-power evidence. Use `0` to disable.

Recommended first real pass:

```bash
--cleanup-mode clean-slate --locked-behavior review --old-vs-new balanced
```

## Outputs

- `dim-import.csv`: DIM-compatible tag/comment import.
- `dim-import-weapons.csv` and `dim-import-armor.csv`: written when both inputs are provided.
- `audit-summary.md`: counts, config, buckets, and recommendations.
- `decisions.json`: structured recommendations, source inputs, and run config.
- `vault-review.html`: local review artifact with filters, ranks, sources, and signal chips.

## Buckets

- `protect`: investment, crafted/exotic state, lock state, or user intent.
- `keep`: useful current roll or role coverage.
- `keep-refarm`: good bridge roll with newer/updated/tiered replacement pressure.
- `replace-now`: weak legacy roll with replacement pressure.
- `needs-review`: conflicting signals, PvP feel, source disagreement, or low confidence.
- `junk`: no current role, protection signal, or bridge value found.

Armor scoring is intentionally cautious. It protects/reviews more than it junks until duplicate grouping and deeper Armor 3.0 rules exist.

## Local Testing Checklist

- Keep real DIM exports out of Git.
- Use `dim-exports/` or `*.private.csv` for real vault files.
- Use `source-cache/` for fetched public source files.
- Start with `--locked-behavior review`.
- Inspect `junk` and `replace-now` rows in HTML before importing anything.
- Treat `dim-import.csv` as proposed metadata, not permission to dismantle.
- Run `git status --short` before committing.

## Repo Map

- `src/auditor/`: CLI and audit engine prototype.
- `scripts/destiny-vault-auditor.py`: no-install CLI wrapper.
- `tests/fixtures/`: synthetic, non-personal fixtures.
- `docs/product-brief.md`: product direction.
- `docs/data-sources.md`: source ranking.
- `docs/audit-model.md`: scoring model.
- `docs/configuration-ux.md`: light config UX.
- `docs/codex-plugin-plan.md`: plugin plan.

## Safety

Do not commit personal DIM exports, Bungie OAuth tokens, API keys, account IDs, or raw vault snapshots.
