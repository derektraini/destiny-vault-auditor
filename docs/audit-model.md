# Audit Model

The auditor should produce explainable recommendations, not absolute truth.

## Primary Buckets

### Protect

Do not demote by default.

Reasons:

- Crafted or reshapeable.
- Weapon level above the configured investment threshold.
- Exotic.
- Holofoil or rare cosmetic version.
- Explicit personal note such as `PVP`, `sentimental`, or `do not delete`.
- In an active loadout.

Prototype thresholds:

- Level `31+`: hard skip / do not demote.
- Level `21-30`: preserve with a comment that says to move on only if the user personally wants a refarm.

### Keep

The roll has a real role today.

Examples:

- Heal Clip + Incandescent.
- Repulsor Brace + Destabilizing Rounds.
- Rimestealer + Headstone.
- Slice + Hatchling.
- Shoot to Loot + Explosive Payload or Kinetic Tremors.
- Envious / Reconstruction / Auto-Loading + Bait and Switch.
- Fourth Time's the Charm + Firing Line or Precision Instrument.
- PvP pairings like Zen Moment + Headseeker, Slideshot + Opening Shot, Snapshot + Opening Shot, Firmly Planted + Tap the Trigger.
- Disorienting grenade launcher with Auto-Loading or Lead from Gold.

### Keep Until Refarmed

The roll is useful, but current data shows a newer/tiered/updated/craftable same-name version.

This is the key bucket for a Monument of Triumph clean-slate vault.

Example:

`KEEP - Bridge roll; destiny.report shows S29 updated tiered version. Refarm before deleting.`

### Replace Now

The roll is weak or duplicate, and a newer/tiered/updated/craftable version exists.

Example:

`JUNK - Weak legacy roll; destiny.report shows S29 updated tiered version.`

### Junk

The roll has no clear PvE, PvP, utility, replacement, investment, or sentimental reason.

Important: `junk` means a DIM metadata tag, not permission to dismantle. The user still reviews before deletion.

### Needs Human Review

Use for ambiguous cases:

- The roll has a personal note but weak objective data.
- The weapon has a unique feel-based PvP role.
- The item is rare, sunset-adjacent, or cosmetic.
- Sources disagree.
- The tool lacks confidence.

## Scoring Inputs

### Item Facts

- Rarity.
- Crafted state.
- Weapon level.
- Gear Tier.
- Season.
- Holofoil.
- Adept.
- Source.
- Ammo type.
- Element.
- Weapon type/frame.
- Perks.
- DIM tag and notes.
- Locked state.
- Power/light level.
- Kill tracker or usage indicators when present.
- Loadout membership.

### Role Coverage

The tool should avoid deleting a user's only coverage for important roles:

- Disorienting grenade launcher.
- Chill Clip / Cold Steel utility.
- Shoot to Loot utility.
- Heal Clip + Incandescent.
- Repulsor + Destabilizing.
- Strand Slice / Hatchling loop.
- Stasis Rimestealer / Headstone loop.
- Boss DPS heavy.
- PvP primary archetype coverage.
- Champion coverage after Anti-Champion 2.0.

### Armor Coverage

Armor should be first-class in the same audit flow, not a separate later tool. Initial armor rules should protect:

- Exotic armor with known build roles.
- Armor 3.0 pieces that cover useful archetype/stat combinations.
- Class items with rare, high-value, or build-defining combinations.
- Pieces referenced by loadouts or personal notes.

Armor comments should explain the build role or replacement reason in the same short style as weapons.

### Replacement Pressure

Use destiny.report and manifest data to detect:

- Same-name newer version.
- Updated version.
- Tiered version.
- Craftable or enhanceable version.
- Known source/farm path.

Replacement pressure should change the comment before it changes the tag. Strong old rolls should often become `keep until refarmed`, not immediate junk.

### Friction And Intent Signals

Some fields should change review priority and confidence more than final scoring. This prevents the tool from turning every vault detail into a separate decision lever.

- Locked: treat as user intent. Do not auto-demote directly to `junk`; prefer `needs review` or a protected comment unless the user enables a strict cleanup mode.
- Lowest power/light level: treat as weak evidence that an item is unused or easy to replace, but never as a sole junk reason.
- Current DIM tag: treat as history, not truth. Existing `favorite` or `keep` should add context but should not protect non-crafted legendary weapons in clean-slate mode.
- Existing DIM `junk`: keep as evidence, but still verify crafted state, level, roll quality, and role coverage before preserving the junk tag.
- High kill count, memento, holofoil, Adept, personal note, or loadout membership: raise protection or review priority.

The default UI should expose this as a single explanation, not a set of toggles. Example:

`REVIEW - Weak duplicate, but locked and has PvP note; confirm before junking.`

### Ranking Model

The product should have an internal ranking system, but the user-facing model should stay simple.

Recommended output levels:

1. `favorite`: best-in-vault, build-defining, rare, or highly invested.
2. `keep`: useful current role or strong bridge roll.
3. `review`: conflicting evidence, personal intent, PvP feel roll, or source disagreement.
4. `junk`: no role, no protection, and no meaningful replacement risk.

Recommended internal dimensions:

- Roll strength.
- Role coverage.
- Replacement pressure.
- Investment/protection.
- Source confidence.
- Review friction.

Only show the detailed dimensions in the HTML artifact when the user expands an item. The CSV comment should stay short.

## Comment Style

Good comments are short, specific, and source-backed.

Preferred pattern:

`<DECISION> - <roll role>; <replacement or protection reason>.`

Examples:

- `KEEP - Heal Clip/Incandescent solar sustain; Tier 5 current copy.`
- `KEEP - PvP feel roll with personal PVP note; test before replacing.`
- `JUNK - Weak legacy duplicate; destiny.report shows updated tiered version.`
- `KEEP - Weapon level 42; high-investment crafted weapon, move on unless refarming intentionally.`

## Clean-Slate Rules From Prototype

The June 10 prototype used these defaults:

- Crafted weapons are preserved.
- Level `>30` weapons are hard preserved.
- Level `>20` weapons get preserve/move-on comments.
- Exotics are preserved.
- Existing `favorite` or `keep` does not protect non-crafted legendaries.
- Non-crafted legendary keepers are converted to `keep`.
- Weak non-crafted legacy weapons can become `junk`.
- destiny.report comments are added without changing the clean-slate tags.
