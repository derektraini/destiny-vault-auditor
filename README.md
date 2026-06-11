# Destiny Vault Auditor

A local-first Destiny 2 vault auditing companion for Codex.

The goal is to turn a DIM vault export, Bungie manifest data, destiny.report old-vs-new signals, and curated meta research into explainable keep/junk/refarm recommendations.

This project is intended for personal use and close friends first. It should be safe, transparent, and reversible: generate review artifacts and DIM import CSVs, never dismantle gear, never move/equip items, and never upload raw vault data unless a user explicitly chooses to share it.

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

## Local Smoke Test

Run the synthetic fixture audit:

```bash
PYTHONPATH=src python -m auditor.cli \
  --weapons-csv tests/fixtures/synthetic_dim_weapons.csv \
  --destiny-report-json tests/fixtures/synthetic_destiny_report.json \
  --out-dir outputs/demo
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Light Audit Config

The CLI supports a small pre-flight config instead of a large settings surface:

```bash
PYTHONPATH=src python -m auditor.cli \
  --weapons-csv tests/fixtures/synthetic_dim_weapons.csv \
  --destiny-report-json tests/fixtures/synthetic_destiny_report.json \
  --out-dir outputs/demo \
  --cleanup-mode clean-slate \
  --locked-behavior review \
  --old-vs-new balanced \
  --pvp-caution balanced
```

Supported posture options:

- `--cleanup-mode`: `gentle`, `clean-slate`, or `aggressive`.
- `--locked-behavior`: `protect`, `review`, or `ignore`.
- `--duplicate-pruning`: `keep-more`, `balanced`, or `prune-hard`.
- `--old-vs-new`: `keep-bridges`, `balanced`, or `prefer-new`.
- `--pvp-caution`: `cautious`, `balanced`, or `strict`.
- `--low-power-below`: note low-power evidence without using it as a sole junk reason.

## Safety Note

This repo should contain source code, docs, sample synthetic fixtures, and anonymized examples only. Do not commit personal DIM exports, Bungie OAuth tokens, API keys, account IDs, or raw vault snapshots.
