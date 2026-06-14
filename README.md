# Destiny Vault Auditor

A local-first Destiny 2 vault auditing companion for Codex.

It reads DIM weapon/armor exports, scores gear with source-backed rules, and generates review artifacts plus a DIM import CSV. It is especially useful for returning players with old vaults who need help deciding what is still worth keeping. It never dismantles, equips, transfers, locks, unlocks, writes to DIM Sync, or uploads vault data.

## Status

Works today:

- Local browser wizard from `python3 scripts/destiny-vault-auditor.py start`.
- Drag/drop or file picker upload for DIM weapons and armor CSVs.
- In-browser review queues, tag/note editing, approval marking, and final DIM import CSV export.
- DIM weapons and armor CSV parsing.
- Optional destiny.report weapon JSON input.
- Optional armor set rating CSV input.
- Optional local wishlist/triage JSON or CSV input.
- Weapon roll scoring with keep/junk/refarm/protect buckets.
- Armor 3.0 scoring for exotics, locked items, notes, investment, class items, stat profiles, archetypes, build roles, set ratings, and useful set/slot coverage.
- Light audit config for cleanup posture.
- Duplicate weapon/armor grouping with a visible HTML duplicate queue.
- Editable HTML review decisions can be imported back into a final DIM CSV.
- Repo-local Codex plugin scaffold and skill wrapper.
- Output files: `dim-import.csv`, `audit-summary.md`, `decisions.json`, `vault-review.html`.

Later ideas:

- Optional source refresh helpers.

See `docs/roadmap.md` for completed milestones and future follow-up ideas.

## Setup

Requirements:

- Python 3.10+.
- Git.
- No install or Python packages are required for the current local workflow.

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

## Friend Quick Start

1. Export weapons and armor CSVs from DIM.
2. Launch the local wizard:

```bash
python3 scripts/destiny-vault-auditor.py start
```

3. Drop or choose the DIM CSV exports in the browser.
4. Review and edit proposed tags/comments.
5. Export `dim-import.csv` from the browser and import it into DIM manually.

The wizard stays local, uses cached files under `source-cache/` when available, and only exports DIM metadata columns: `Name`, `Hash`, `Id`, `Tag`, and `Notes`. It does not dismantle, move, lock, unlock, or write to DIM Sync.

## Quick Start

Launch the local wizard:

```bash
python3 scripts/destiny-vault-auditor.py start
```

Run the synthetic fixture audit from the advanced CLI:

```bash
python3 scripts/destiny-vault-auditor.py \
  --weapons-csv tests/fixtures/synthetic_dim_weapons.csv \
  --armor-csv tests/fixtures/synthetic_dim_armor.csv \
  --destiny-report-json tests/fixtures/synthetic_destiny_report.json \
  --armor-set-ratings-csv tests/fixtures/synthetic_armor_set_ratings.csv \
  --wishlist-source tests/fixtures/synthetic_wishlist.json \
  --out-dir outputs/demo
```

Open the review artifact:

```bash
open outputs/demo/vault-review.html
```

## Real DIM Export

Export weapons and armor from DIM, then run:

```bash
python3 scripts/destiny-vault-auditor.py start
```

The browser wizard detects weapons vs armor automatically, applies the same audit engine as the CLI, and exports the final DIM import CSV after review.

Advanced CLI runs can still read CSVs from an ignored/private path such as `dim-exports/`.

```bash
mkdir -p dim-exports
```

Name the files `weapons.private.csv` and `armor.private.csv` for the easiest advanced CLI path. The CLI will auto-detect those files:

```bash
python3 scripts/destiny-vault-auditor.py \
  --out-dir outputs/my-audit \
  --cleanup-mode clean-slate \
  --locked-behavior review
```

You can also drag CSV files into the command instead of naming flags manually:

```bash
python3 scripts/destiny-vault-auditor.py ~/Downloads/dim-weapons.csv ~/Downloads/dim-armor.csv \
  --out-dir outputs/my-audit
```

The CLI refuses unignored CSV inputs inside the repo by default. Files under `dim-exports/` and `*.private.csv` are ignored by Git.

Optional armor set source:

```bash
mkdir -p source-cache
curl -L "https://docs.google.com/spreadsheets/d/14LnzOhmeXzKaSV3OR35pQJkclg6vLC4YmKtlKTctY3o/export?format=csv&gid=631213508" \
  -o source-cache/armor-set-ratings.csv
```

Optional wishlist/triage source:

```json
{
  "source_name": "My local triage notes",
  "entries": [
    {
      "name": "Example Weapon",
      "source_date": "2026-06-01",
      "role": "PvE utility",
      "recommended_combos": [["Perk A", "Perk B"]],
      "notes": "Why this roll matters."
    }
  ]
}
```

CSV sources can use columns such as `name`, `hash`, `role`, `recommended_combos`, `source_name`, `author`, `source_date`, `confidence`, and `notes`. Separate multiple combos with semicolons and perks inside a combo with `+`.

Optional destiny.report source:

`--destiny-report-json` expects a JSON file that already exists on disk. If you do not have one, leave that flag out; the auditor still runs from DIM exports.

Run an audit with only the optional files you actually have:

```bash
python3 scripts/destiny-vault-auditor.py \
  --armor-set-ratings-csv source-cache/armor-set-ratings.csv \
  --out-dir outputs/my-audit \
  --cleanup-mode clean-slate \
  --locked-behavior review \
  --duplicate-pruning balanced \
  --old-vs-new balanced \
  --pvp-caution balanced
```

Without optional source files:

```bash
python3 scripts/destiny-vault-auditor.py \
  --out-dir outputs/my-audit
```

Review `outputs/my-audit/vault-review.html` before importing any CSV into DIM. If you edit tags or comments in the standalone HTML artifact, rerun with `--review-decisions-json` and import the second-pass `outputs/my-final-audit/dim-import.csv`. The `start` wizard does this second pass internally when you export the DIM CSV.

## Returning Player Flow

1. Export both weapons and armor from DIM.
2. Run `python3 scripts/destiny-vault-auditor.py start`.
3. Drop the DIM CSVs into the browser.
4. Start review with `junk`, `replace-now`, `needs-review`, and duplicate groups.
5. Edit tags/comments in the browser.
6. Export the final DIM CSV from the browser.
7. Import the final DIM CSV only after the recommendations make sense.

The tool ranks and categorizes gear using vault facts, current-ish source metadata, perk/set heuristics, and personal-intent signals like locks, notes, crafted state, and weapon level.

Advanced second pass after standalone HTML review:

```bash
python3 scripts/destiny-vault-auditor.py \
  --armor-set-ratings-csv source-cache/armor-set-ratings.csv \
  --review-decisions-json ~/Downloads/decisions.json \
  --out-dir outputs/my-final-audit
```

## Config

- `--weapons-csv`: DIM weapons CSV export.
- `--armor-csv`: DIM armor CSV export.
- `--destiny-report-json`: optional destiny.report weapon JSON export.
- `--armor-set-ratings-csv`: optional armor set bonus rating sheet CSV.
- `--wishlist-source`: optional local wishlist/triage JSON or CSV source.
- `--review-decisions-json`: optional edited decisions JSON exported from `vault-review.html`.
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

- `dim-import.csv`: DIM-compatible tag/comment import with `Name`, `Hash`, `Id`, `Tag`, and `Notes`.
- `dim-import-weapons.csv` and `dim-import-armor.csv`: written when both inputs are provided.
- `audit-summary.md`: counts, config, buckets, and recommendations.
- `decisions.json`: structured recommendations, duplicate group metadata, source inputs, and run config.
- `vault-review.html`: local review artifact with filters, ranks, duplicate queue, sources, and signal chips.

## Codex Plugin

The repo includes a local plugin scaffold under `plugin/destiny-vault-auditor/`.

The plugin contributes a `destiny-vault-auditor` skill and a wrapper command:

```bash
python3 plugin/destiny-vault-auditor/scripts/audit_vault.py --help
```

The wrapper delegates to `scripts/destiny-vault-auditor.py`, so the no-install CLI remains the source of truth. The plugin does not add OAuth, DIM Sync writes, browser automation, or any direct gear actions.

## Buckets

- `protect`: investment, crafted/exotic state, lock state, or user intent.
- `keep`: useful current roll or role coverage.
- `keep-refarm`: good bridge roll with newer/updated/tiered replacement pressure.
- `replace-now`: weak legacy roll with replacement pressure.
- `needs-review`: conflicting signals, PvP feel, source disagreement, or low confidence.
- `junk`: no current role, protection signal, or bridge value found.

Armor scoring is intentionally cautious. It combines set ratings, stat fit, archetype/build-role signals, and only-copy set/slot coverage before suggesting cleanup.

## Local Testing Checklist

- Keep real DIM exports out of Git.
- Use `dim-exports/` or `*.private.csv` for real vault files.
- Use `source-cache/` for fetched public source files.
- Start with `--locked-behavior review`.
- Inspect `junk` and `replace-now` rows in HTML before importing anything.
- Treat `dim-import.csv` as proposed metadata, not permission to dismantle.
- Run `git status --short` before committing.

## Repo Map

- `src/auditor/`: CLI and audit engine.
- `scripts/destiny-vault-auditor.py`: no-install CLI wrapper.
- `tests/fixtures/`: synthetic, non-personal fixtures.
- `docs/product-brief.md`: product direction.
- `docs/data-sources.md`: source ranking.
- `docs/audit-model.md`: scoring model.
- `docs/configuration-ux.md`: light config UX.
- `docs/codex-plugin-plan.md`: plugin plan.
- `docs/friend-testing.md`: short share guide for testers.
- `docs/roadmap.md`: completed milestones and future follow-up ideas.

## Safety

Do not commit personal DIM exports, Bungie OAuth tokens, API keys, account IDs, or raw vault snapshots.
