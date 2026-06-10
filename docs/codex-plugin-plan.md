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

1. User provides DIM CSV exports or a folder containing exports.
2. Plugin asks whether to refresh public source data.
3. Plugin runs the audit engine.
4. Plugin generates:
   - `outputs/audit-summary.md`
   - `outputs/vault-review.html`
   - `outputs/dim-import.csv`
   - `outputs/decisions.json`
5. User reviews the HTML artifact.
6. Plugin consumes the decision JSON and writes the final DIM import.

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
- Optionally use read-only Bungie OAuth later if the user configures it.

## Future Read-Only Bungie Integration

When ready, add optional Bungie OAuth for read-only inventory snapshots.

Use only the minimum needed scope for private Destiny reads. The MVP should still support CSV-only operation so friends can use it without registering an app.

## Implementation Phases

### Phase 1: File-Based Prototype

- Parse DIM weapon CSV.
- Parse destiny.report weapon JSON.
- Produce markdown summary and DIM import CSV.
- Unit test scoring rules with synthetic fixtures.

### Phase 2: Review Artifact

- Generate `vault-review.html`.
- Add interactive filters and decision toggles.
- Export decision JSON.
- Regenerate final DIM CSV from reviewed decisions.

### Phase 3: Armor

- Add Armor 3.0 archetype logic.
- Support exotic armor build roles.
- Add duplicate class item cleanup.

### Phase 4: Codex Plugin Packaging

- Add `.codex-plugin/plugin.json`.
- Add skill instructions.
- Provide clear prompts/commands for Codex Web.

### Phase 5: Optional Live Data

- Optional Bungie OAuth read-only snapshot.
- Optional source refresh cache.
- Optional Dia/DIM browser automation for import verification.
