# Destiny Vault Auditor

A local-first Destiny 2 vault auditing companion for Codex.

It reads DIM exports, scores weapons with source-backed rules, and generates review artifacts plus a DIM import CSV. It never dismantles, equips, transfers, locks, unlocks, writes to DIM Sync, or uploads vault data.

## Status

Works today:

- DIM weapons CSV parsing.
- Optional destiny.report weapon JSON input.
- Weapon roll scoring with keep/junk/refarm/protect buckets.
- Light audit config for cleanup posture.
- Output files: `dim-import.csv`, `audit-summary.md`, `decisions.json`, `vault-review.html`.

Planned:

- Armor CSV parsing and Armor 3.0 scoring.
- Duplicate grouping.
- Wishlist/triage source ingestion.
- Codex plugin packaging.
- Import reviewed HTML decisions back into final CSV generation.

## Setup

Requirements:

- Python 3.10+.
- Git.
- No Python packages are required for the current prototype.

Clone and enter the repo:

```bash
git clone https://github.com/derektraini/destiny-vault-auditor.git
cd destiny-vault-auditor
```

Optional virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Verify the CLI works:

```bash
PYTHONPATH=src python3 -m auditor.cli --help
python3 -m unittest discover -s tests
```

## Quick Start

Run the synthetic fixture audit:

```bash
PYTHONPATH=src python3 -m auditor.cli \
  --weapons-csv tests/fixtures/synthetic_dim_weapons.csv \
  --destiny-report-json tests/fixtures/synthetic_destiny_report.json \
  --out-dir outputs/demo
```

Open the review artifact:

```bash
open outputs/demo/vault-review.html
```

## Real DIM Export

Export weapons from DIM and put the CSV in an ignored/private path such as `dim-exports/`.

```bash
mkdir -p dim-exports
```

Run an audit:

```bash
PYTHONPATH=src python3 -m auditor.cli \
  --weapons-csv dim-exports/weapons.private.csv \
  --destiny-report-json path/to/destiny-report-weapons.json \
  --out-dir outputs/my-audit \
  --cleanup-mode clean-slate \
  --locked-behavior review \
  --duplicate-pruning balanced \
  --old-vs-new balanced \
  --pvp-caution balanced
```

Without destiny.report data:

```bash
PYTHONPATH=src python3 -m auditor.cli \
  --weapons-csv dim-exports/weapons.private.csv \
  --out-dir outputs/my-audit
```

Review `outputs/my-audit/vault-review.html` before importing `outputs/my-audit/dim-import.csv` into DIM.

## Config

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
- `audit-summary.md`: counts, config, buckets, and recommendations.
- `decisions.json`: structured recommendations and run config.
- `vault-review.html`: local review artifact with filters, ranks, sources, and signal chips.

## Buckets

- `protect`: investment, crafted/exotic state, lock state, or user intent.
- `keep`: useful current roll or role coverage.
- `keep-refarm`: good bridge roll with newer/updated/tiered replacement pressure.
- `replace-now`: weak legacy roll with replacement pressure.
- `needs-review`: conflicting signals, PvP feel, source disagreement, or low confidence.
- `junk`: no current role, protection signal, or bridge value found.

## Local Testing Checklist

- Keep real DIM exports out of Git.
- Start with `--locked-behavior review`.
- Inspect `junk` and `replace-now` rows in HTML before importing anything.
- Treat `dim-import.csv` as proposed metadata, not permission to dismantle.
- Run `git status --short` before committing.

## Repo Map

- `src/auditor/`: CLI and audit engine prototype.
- `tests/fixtures/`: synthetic, non-personal fixtures.
- `docs/product-brief.md`: product direction.
- `docs/data-sources.md`: source ranking.
- `docs/audit-model.md`: scoring model.
- `docs/configuration-ux.md`: light config UX.
- `docs/codex-plugin-plan.md`: plugin plan.

## Safety

Do not commit personal DIM exports, Bungie OAuth tokens, API keys, account IDs, or raw vault snapshots.
