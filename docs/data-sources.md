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

These sources can answer "what are players excited about?" but not always "what is actually best for this vault?"

## Source Ranking

1. Bungie manifest/API facts.
2. Current patch notes.
3. destiny.report current weapon metadata.
4. D2Foundry / Clarity-style mechanics and perk data.
5. User vault metadata: crafted state, weapon level, notes, kill counts, holofoil, loadouts.
6. Community meta and popularity.

## Provenance Requirement

Every generated comment should include enough provenance to explain the recommendation without being noisy.

Example:

`KEEP - Strong PvP roll; destiny.report shows S29 tiered replacement, keep until refarmed.`

Example:

`JUNK - No current 9.7.0 role; newer updated/tiered same-name version exists.`
