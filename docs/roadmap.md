# Roadmap

This roadmap turns the remaining planned items into buildable milestones. The goal is to keep the tool useful for returning players without making vault cleanup feel like homework.

## Recommended Order

1. Deeper Armor 3.0 archetype/build scoring.
2. Codex plugin packaging.

## Completed: Reviewed Decisions To Final CSV

Status: implemented.

Why it mattered: this closes the loop between review and DIM import. The generated HTML can export edited decisions, and the CLI can now consume those decisions to regenerate the final `dim-import.csv`.

Implemented:

- Added `--review-decisions-json`.
- Read edited decisions from the HTML artifact export.
- Match decisions by `Id`, falling back to `Hash` only when needed.
- Regenerate `dim-import.csv` from approved/edited decisions.
- Preserve original notes while replacing old `DVA:` audit comments.
- Warn on stale or ambiguous decisions.

Acceptance criteria:

- A tester can run audit, review HTML, export decisions JSON, rerun CLI, and import a final DIM CSV.
- Manual changes to tag/comment survive into the final CSV.
- Missing or stale item IDs produce review warnings, not silent bad imports.

## Completed: Duplicate Grouping

Status: implemented.

Why it mattered: duplicate cleanup is one of the highest-value vault wins, especially for returning players with multiple old versions of the same weapon or redundant armor pieces.

Implemented:

- Group weapons by normalized name and type.
- Group armor by slot, set name, rarity, and broad stat shape.
- Pick a best-in-group candidate using bucket/tag/confidence, crafted state, tier, weapon level, lock/note signals, armor totals, and set ratings.
- Add duplicate metadata and `duplicate-group`, `duplicate-best`, and `duplicate-copy` signal chips to decisions and HTML.
- Add a visible HTML duplicate queue.
- Preserve at least one non-junk copy in a duplicate group.

Acceptance criteria:

- The summary reports duplicate group counts.
- The HTML artifact has a duplicate queue.
- The auditor never junks every copy in a role group unless strict mode is explicit.

## Completed: Wishlist And Triage Source Ingestion

Status: implemented.

Why it mattered: wishlist notes provide the missing "why this roll exists" layer. They help distinguish god rolls from utility rolls, PvP feel rolls, and niche endgame tools.

Implemented:

- Added `--wishlist-source` for local JSON or CSV files.
- Support source metadata: source name, author, date, context, confidence, role, notes, and recommended combos.
- Match weapons by hash or normalized name plus perk combos.
- Add `wishlist-match`, `wishlist-partial`, `wishlist-stale`, and `wishlist-role:*` signals.
- Exact fresh matches can strengthen weak recommendations into `keep`.
- Partial or stale matches route to review and explain why.

Acceptance criteria:

- Exact curated matches strengthen `keep` or `favorite`.
- Partial matches route to `needs-review`, not automatic keep.
- Stale sources are visible and lower confidence when patch/source dates are old.

## 4. Deeper Armor 3.0 Archetype And Build Scoring

Why fourth: armor needs more context before it should get aggressive. The current version is intentionally conservative and relies on exotics, notes, locks, investment, stat shape, and set ratings.

First useful version:

- Parse armor slot, set name, class, archetype, stat totals, and stat spikes from DIM exports where available.
- Add build roles such as survival, grenade, melee, weapon-stat, PvP, raid/dungeon set utility, and class-item cleanup.
- Use armor set rating sheets as a source, but combine them with stats and user intent.
- Detect "only copy of useful set/slot" before junking.
- Keep class items cautious until duplicate/build context is better.

Acceptance criteria:

- Armor recommendations explain set value plus stat fit.
- Low-stat, low-rated, unlocked, unnoted legendary armor can become `junk`.
- Useful set pieces with weak stats become `needs-review`, not blind keep.

## 5. Codex Plugin Packaging

Why last: packaging should wrap a reliable local workflow. It should not hide rough edges before the CLI and review loop are trustworthy.

First useful version:

- Add plugin metadata and a skill wrapper.
- Provide a single Codex entrypoint that asks for DIM exports and optional source files.
- Run the CLI safely.
- Open or link the generated review artifact.
- Point users at the final `dim-import.csv`.

Acceptance criteria:

- A friend can use Codex to run the audit without learning internal commands.
- The plugin still keeps all private exports local and ignored.
- The plugin does not request OAuth or write to DIM.

## Non-Goals For The Next Pass

- Automatic DIM import.
- Bungie OAuth.
- Dismantle recommendations without human review.
- Perfect armor buildcraft scoring.
- Hosted web app.
