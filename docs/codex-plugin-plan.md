# Codex Plugin Plan

## Distribution

Start as a Codex plugin or skill, not a hosted website.

The plugin should be usable from Codex Web by reading this repo, and later from a local Mac when we want to test DIM browser flows.

## Proposed Repo Shape

```text
destiny-vault-auditor/
  README.md
  docs/
  plugin/
    .codex-plugin/
      plugin.json
    skills/
      destiny-vault-auditor/
        SKILL.md
        scripts/
          audit_vault.py
          fetch_sources.py
          build_review_artifact.py
        templates/
          vault-review.html
  src/
    auditor/
      dim_csv.py
      destiny_report.py
      manifest.py
      scoring.py
      comments.py
      review_artifact.py
  tests/
    fixtures/
      synthetic_dim_weapons.csv
      synthetic_destiny_report.json
```

The exact layout can change once implementation starts. The key is to keep the audit engine separate from the Codex skill wrapper.

## Plugin Workflow

1. User provides DIM weapon and armor CSV exports, or a folder containing exports.
2. Plugin uses cached structured source data and asks whether to refresh current public/meta sources.
3. Plugin runs the audit engine.
4. Plugin generates:
   - `outputs/audit-summary.md`
   - `outputs/vault-review.html`
   - `outputs/decisions.json`
5. User reviews the HTML artifact and exports reviewed decisions JSON.
6. Plugin consumes the reviewed decision JSON and writes the final DIM import CSV.

The MVP is DIM CSV only. OAuth, DIM Sync writes, and direct inventory actions are excluded from the core workflow.

## HTML Review Artifact

The HTML artifact should be a self-contained local file with embedded JSON.

Useful views:

- Overview dashboard.
- Replace-now queue.
- Keep-until-refarmed queue.
- Crafted/high-level protected queue.
- PvP/personal-note queue.
- Duplicate groups.
- Armor build coverage.
- Source confidence and provenance.

Useful controls:

- Filter by bucket, weapon type, ammo, element, source, tier, crafted state.
- Toggle decisions item by item.
- Bulk approve a bucket.
- Mark preference rules such as:
  - preserve holofoils
  - preserve PvP notes
  - keep one of each exotic
  - keep only best same-name duplicate
  - go hard on S29 updated/tiered replacements
- Export reviewed decisions as JSON.

The artifact should not need a server. It should work from `file://` or a tiny local server if browser restrictions require it.

## Safety Model

The plugin should never:

- Dismantle gear.
- Transfer gear.
- Equip gear.
- Lock or unlock gear.
- Write to DIM Sync directly.
- Store OAuth tokens in the repo.

The plugin may:

- Read local CSV files.
- Download public source data.
- Generate local reports.
- Generate DIM import CSVs.
- Store local, ignored run artifacts and preference profiles.

## Out Of MVP

Read-only Bungie OAuth may be useful later for convenience, but the current product decision is to keep the MVP CSV-only so it works for personal use and close friends without app registration.

## Implementation Phases

### Phase 1: File-Based Prototype

- Parse DIM weapon CSV.
- Parse DIM armor CSV.
- Parse destiny.report weapon JSON.
- Produce markdown summary and DIM import CSV.
- Unit test scoring rules with synthetic fixtures.

### Phase 2: Review Artifact

- Generate `vault-review.html`.
- Add interactive filters and decision toggles.
- Export decision JSON.
- Regenerate final DIM CSV from reviewed decisions.

### Phase 3: Armor Depth

- Add Armor 3.0 archetype logic.
- Support exotic armor build roles.
- Add duplicate class item cleanup.

### Phase 4: Codex Plugin Packaging

- Add `.codex-plugin/plugin.json`.
- Add skill instructions.
- Provide clear prompts/commands for Codex Web.

### Phase 5: Optional Live Data

- Optional source refresh cache.
- Optional Dia/DIM browser automation for import verification.
