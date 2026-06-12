# Data Sources

This tool should make source-backed recommendations. No single source should get final say.

## Canonical Sources

### Bungie API And Manifest

Use for canonical item definitions, plugs, sockets, stats, collectibles, vendors, and activity definitions.

Useful docs:

- https://bungie-net.github.io/
- https://github.com/Bungie-net/api

Relevant access model:

- Public manifest data requires an API key.
- Private Destiny 2 profile and vault reads use OAuth with `ReadDestinyInventoryAndVault`.
- Private profile reads, write scopes, and item actions should not be used for the MVP.

### DIM CSV Export/Import

Use for the MVP because it is simple, user-mediated, reversible, and works for close friends without Bungie app setup.

Primary fields used in the prototype:

- `Name`
- `Hash`
- `Id`
- `Tag`
- `Notes`
- `Rarity`
- `Tier`
- `Type`
- `Element`
- `Ammo`
- `Crafted`
- `Crafted Level`
- `Holofoil`
- `Season`
- `Perks 0..n`

The MVP should continue to produce a DIM-compatible CSV rather than writing tags directly.

Also preserve and inspect any DIM metadata that expresses user intent:

- Locked state.
- Current tag.
- Notes.
- Wishlist/triage annotations.
- Kill trackers when present.
- Power/light level.
- Loadout references if available from an export path.

### destiny.report

Use for old-vs-new replacement pressure.

The June 10 prototype confirmed destiny.report exposes a current weapon database with useful fields:

- `hash`
- `name`
- `season`
- `source`
- `sourceString`
- `isTiered`
- `isCraftable`
- `isUpdated`
- `isEnhanceable`
- `isAdept`
- `isHolofoil`
- perk socket pools

This is especially useful for comments like:

- `newer/updated version exists; move on/refarm`
- `keep only until replaced`
- `exact hash is already modern/tiered/craftable`

Source:

- https://destiny.report/

## Strong Supporting Sources

### D2Foundry

Use for roll inspection, perk pools, stat packages, enhanced/crafted state, and human-readable weapon comparison.

Source:

- https://d2foundry.gg/

### Clarity / Perk Behavior Data

Use for exact perk behavior, hidden mechanics, cooldowns, scalar values, and practical effect descriptions. This should be treated as a high-quality mechanics source when available.

### Armor Set Rating Sheets

Use curated armor set bonus sheets as supporting armor sources. These should influence recommendations when a DIM export exposes a matching set name, but they should not override personal notes, locked state, exotics, or strong stat profiles by themselves.

Current supported sheet:

- https://docs.google.com/spreadsheets/d/14LnzOhmeXzKaSV3OR35pQJkclg6vLC4YmKtlKTctY3o/htmlview?gid=631213508

### Curated Wishlists And Triage Notes

Use curated wishlists, DIM wishlist notes, and triage panels as source-backed opinion layers. These sources are valuable because they often encode:

- Intended role, such as PvE, PvP, utility, add clear, boss DPS, endgame, or minor spec.
- Input context, such as M+KB or controller.
- Recommended perk combinations.
- Explanation for why a roll matters.
- Source author, episode, guide, or publication date.

Treat these as curated community evidence, not canonical truth. Current patch notes, manifest facts, and mechanics data should override stale wishlist guidance when they conflict.

Example source shape:

```json
{
  "source": "wishlist",
  "source_name": "PodvsEnemies episode 129 / Saint_Kabr / ImpetusAlways / CourtProjects",
  "source_date": "2024-02-04",
  "contexts": ["PvE", "PvE-Utility", "PvE-EndGame", "MinorSpec"],
  "input_devices": ["M+KB", "Controller"],
  "recommended_combos": [
    ["Reciprocity", "Circle of Life"],
    ["Reciprocity", "Attrition Orbs"],
    ["Reciprocity", "Frenzy"]
  ]
}
```

Wishlist matches should improve the recommendation and comment quality. They should not silently protect a bad or obsolete roll forever.

Current supported input:

- `--wishlist-source path/to/source.json`
- `--wishlist-source path/to/source.csv`

Supported fields include `name`, `hash`, `role`, `recommended_combos`, `source_name`, `author`, `source_date`, `confidence`, `contexts`, and `notes`.

Exact fresh matches can strengthen a weapon to `keep`. Partial matches and stale matches route to review so the user sees the evidence without treating older community guidance as current truth.

### Patch Notes

Patch notes should override stale community consensus.

For the prototype, Destiny Update 9.7.0 mattered because it changed:

- Tiered raid/dungeon rewards.
- Crafted weapons with Enhanced Intrinsics reaching Gear Tier 5 power.
- Intrinsic anti-Champion behavior by weapon archetype/frame.
- Primary, special, and heavy weapon damage tuning.
- Perk buffs and reworks such as Focused Fury, Full Court, Lasting Impression, Reservoir Burst, Attrition Orbs, and Desperado.
- Armor 3.0 archetypes.

Source:

- https://www.bungie.net/7/en/News/Article/destiny_update_9_7_0

## Softer Community Signals

These are useful but should not be treated as truth by themselves:

- light.gg popularity and roll appraiser data.
- YouTube creator meta videos.
- Reddit/X discussion.
- Raid/dungeon/trials usage trends.
- Trials/PvP usage data and input-specific creator guidance.

These sources can answer "what are players excited about?" but not always "what is actually best for this vault?"

## Source Ranking

1. Bungie manifest/API facts.
2. Current patch notes.
3. destiny.report current weapon metadata.
4. D2Foundry / Clarity-style mechanics and perk data.
5. Armor set rating sheets with dates and provenance.
6. User vault metadata: crafted state, weapon level, notes, kill counts, holofoil, loadouts.
7. Curated wishlist/triage notes with dates and provenance.
8. Community meta and popularity.

## Provenance Requirement

Every generated comment should include enough provenance to explain the recommendation without being noisy.

Example:

`KEEP - Strong PvP roll; destiny.report shows S29 tiered replacement, keep until refarmed.`

Example:

`JUNK - No current 9.7.0 role; newer updated/tiered same-name version exists.`
