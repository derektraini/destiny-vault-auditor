# Destiny Vault Auditor

A local-first Destiny 2 vault auditing companion for Codex.

The goal is to turn DIM vault exports, Bungie manifest data, destiny.report old-vs-new signals, curated wishlist/meta sources, and local preferences into explainable keep/junk/refarm recommendations.

This project is intended for personal use and close friends first. It should be safe, transparent, and reversible: generate review artifacts and DIM import CSVs, never dismantle gear, never move/equip items, and never upload raw vault data unless a user explicitly chooses to share it.

## What Works Today

The current prototype can:

- Read a DIM weapons CSV.
- Read a destiny.report weapon JSON export.
- Score weapon rolls into recommendation buckets.
- Preserve crafted, exotic, high-level, locked, and user-intent items according to config.
- Account for same-name newer/updated/tiered replacement pressure.
- Generate a DIM import CSV with proposed tags and comments.
- Generate `audit-summary.md`, `decisions.json`, and `vault-review.html`.
- Show light audit posture in the HTML artifact: cleanup mode, lock behavior, old-vs-new pressure, PvP caution, and low-power threshold.

Planned next:

- Armor CSV parsing and Armor 3.0 scoring.
- Real duplicate grouping.
- Curated wishlist/triage source ingestion.
- Codex plugin packaging.
- Reviewed-decision import back into final CSV generation.

## Quick Start

Run the synthetic fixture audit:

```bash
PYTHONPATH=src python -m auditor.cli \
  --weapons-csv tests/fixtures/synthetic_dim_weapons.csv \
  --destiny-report-json tests/fixtures/synthetic_destiny_report.json \
  --out-dir outputs/demo
```

Open the generated review artifact:

```bash
open outputs/demo/vault-review.html
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Usage With A Real DIM Weapons CSV

Export weapons from DIM, keep the file outside Git or under an ignored folder such as `dim-exports/`, then run:

```bash
PYTHONPATH=src python -m auditor.cli \
  --weapons-csv dim-exports/weapons.private.csv \
  --destiny-report-json path/to/destiny-report-weapons.json \
  --out-dir outputs/my-audit \
  --cleanup-mode clean-slate \
  --locked-behavior review \
  --duplicate-pruning balanced \
  --old-vs-new balanced \
  --pvp-caution balanced \
  --low-power-below 0
```

Review `outputs/my-audit/vault-review.html` first. Import `outputs/my-audit/dim-import.csv` into DIM only after the recommendations look right.

If you do not have a destiny.report JSON yet, omit that flag. The audit will still run, but it will not have old-vs-new replacement pressure:

```bash
PYTHONPATH=src python -m auditor.cli \
  --weapons-csv dim-exports/weapons.private.csv \
  --out-dir outputs/my-audit
```

## Before Testing Locally

- Keep real DIM exports in `dim-exports/` or another ignored/private path.
- Start with a small or synthetic export if you want to inspect the output shape first.
- Use `--locked-behavior review` for the first real pass.
- Open `vault-review.html` and inspect `junk` plus `replace-now` rows before importing anything.
- Treat `dim-import.csv` as proposed metadata, not permission to dismantle.
- Run `git status --short` before committing anything and make sure no private CSVs or personal outputs are staged.

## Outputs

- `dim-import.csv` - DIM-compatible tag/comment import.
- `audit-summary.md` - readable counts, config, buckets, and recommendation list.
- `decisions.json` - structured recommendations and run config for Codex/plugin handoff.
- `vault-review.html` - local interactive review artifact with filters, rank, sources, and intent-signal chips.

## Light Audit Config

The CLI supports a small pre-flight config instead of a large settings surface:

- `--cleanup-mode`: `gentle`, `clean-slate`, or `aggressive`.
- `--high-level`: weapon level above this is protected. Default: `30`.
- `--invested-level`: weapon level above this gets investment context. Default: `20`.
- `--locked-behavior`: `protect`, `review`, or `ignore`.
- `--duplicate-pruning`: `keep-more`, `balanced`, or `prune-hard`.
- `--old-vs-new`: `keep-bridges`, `balanced`, or `prefer-new`.
- `--pvp-caution`: `cautious`, `balanced`, or `strict`.
- `--low-power-below`: note low-power evidence without using it as a sole junk reason. Use `0` to disable.

Recommended first local test:

```bash
PYTHONPATH=src python -m auditor.cli \
  --weapons-csv dim-exports/weapons.private.csv \
  --destiny-report-json path/to/destiny-report-weapons.json \
  --out-dir outputs/clean-slate \
  --cleanup-mode clean-slate \
  --locked-behavior review \
  --old-vs-new balanced
```

## Recommendation Buckets

- `protect`: preserve by default because of investment, crafted/exotic state, lock state, or other user intent.
- `keep`: useful current roll or role coverage.
- `keep-refarm`: good bridge roll, but a newer/updated/tiered version exists.
- `replace-now`: weak legacy roll with replacement pressure.
- `needs-review`: conflicting signals, PvP feel, locked weak roll, source disagreement, or low confidence.
- `junk`: no current role, protection signal, or replacement-bridge value found.

The generated DIM tag is intentionally simpler than the internal bucket: usually `favorite`, `keep`, or `junk`.

## Current Limitations

- The code prototype currently audits weapons only, even though the product direction is weapons plus armor.
- `--duplicate-pruning` is recorded in config but does not yet run true duplicate-group logic.
- Wishlist/triage sources are documented but not ingested yet.
- destiny.report fetching is not automated in the CLI yet; provide a JSON export/path.
- The HTML artifact exports reviewed decisions JSON, but the follow-up step that consumes edited decisions and regenerates the final DIM CSV is still planned.
- Recommendations are metadata only. The tool never dismantles, equips, transfers, locks, unlocks, or writes to DIM Sync.

## Product Shape

The preferred distribution is a Codex plugin or skill backed by a reusable local audit engine.

The plugin should generate:

- A markdown summary for quick reading.
- A local HTML review artifact for interactive decisions.
- A DIM-compatible import CSV with proposed tags and comments.
- A decision log JSON that Codex can consume to generate the final DIM import.

## Why Not A Hosted Website First?

A hosted website would add privacy, authentication, and trust friction. The safer first version is local/file-based:

1. User exports DIM weapon and armor CSVs.
2. Codex/plugin refreshes public source data.
3. The audit engine stages recommendations.
4. A local HTML artifact lets the user review edge cases.
5. The user imports the final CSV into DIM manually.

A website or PWA can come later, but the engine should not depend on hosting.

## Core Principles

- Read-only by default.
- No raw vault exports committed to Git.
- No destructive Destiny actions.
- Explain every recommendation with source-backed reasons.
- Treat old favorites as evidence, not truth.
- Preserve crafted, high-investment, exotic, sentimental, and PvP-feel exceptions unless the user opts into stricter pruning.
- Prefer current/tiered/updated gear when destiny.report or manifest data shows replacement pressure.

## Current Status

Initial product discovery and a prototype audit were done on June 10, 2026 around Destiny Update 9.7.0 / Monument of Triumph.

The prototype proved that the workflow is viable:

- DIM CSV exports can be parsed and rewritten with tags/comments.
- Bungie Update 9.7.0 materially changes keep/junk logic.
- destiny.report exposes a useful current weapon database with same-name version, tiered, craftable, updated, source, and season metadata.
- A second-pass clean-slate audit is more useful than preserving existing DIM favorite/keep tags blindly.
- A local HTML review artifact would be the right UI for resolving questions before producing the final DIM import.
- The MVP should cover both weapons and armor, with the current code prototype starting on weapons first.

See the docs in `docs/` for the product brief, source strategy, audit model, and Codex plugin plan.

## Repository Contents

- `docs/product-brief.md` - what this tool should become.
- `docs/data-sources.md` - source ranking and integration notes.
- `docs/audit-model.md` - recommendation buckets and scoring logic.
- `docs/configuration-ux.md` - the light pre-flight config and review flow.
- `docs/codex-plugin-plan.md` - local plugin and artifact architecture.
- `docs/research-snapshot-2026-06-10.md` - summary of the research and prototype findings so far.
- `src/auditor/` - first local audit engine prototype.
- `tests/fixtures/` - synthetic, non-personal CSV/JSON fixtures.

## Safety Note

This repo should contain source code, docs, sample synthetic fixtures, and anonymized examples only. Do not commit personal DIM exports, Bungie OAuth tokens, API keys, account IDs, or raw vault snapshots.
