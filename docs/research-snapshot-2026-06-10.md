# Research Snapshot - 2026-06-10

## Context

This snapshot summarizes the product discovery and prototype audit work done around Destiny 2 Update 9.7.0 / Monument of Triumph.

The user goal was to enter the update with a cleaner vault and a better rule than "preserve whatever was already tagged favorite."

## Major Gameplay Context From 9.7.0

Update 9.7.0 changed vault logic because it introduced or emphasized:

- Tiered rewards from pre-Edge of Fate raids and dungeons.
- Featured raids/dungeons dropping Tier 5 weapons and armor.
- Craftable raid weapons with Enhanced Intrinsics reaching Gear Tier 5 power.
- Intrinsic anti-Champion behavior by archetype/frame.
- Broad primary weapon PvE buffs.
- Special and heavy weapon tuning.
- Perk buffs/reworks including Focused Fury, Full Court, Lasting Impression, Reservoir Burst, Collective Action, Adagio, Attrition Orbs, Desperado, and Jolting Feedback.
- Armor 3.0 archetypes and new archetype families.

Primary source:

- https://www.bungie.net/7/en/News/Article/destiny_update_9_7_0

## Prototype Workflow

The prototype used DIM CSV exports and generated staged DIM import CSVs with updated tags/comments.

The first pass was conservative and preserved existing `favorite` or `keep` tags unless a rule explicitly forced junk. That was useful as a safe first pass, but it was not a true clean-slate audit.

The second pass changed the rule:

- Crafted weapons were preserved.
- High-level weapons were preserved.
- Exotics were preserved.
- Existing `favorite` or `keep` tags no longer protected non-crafted legendary weapons.
- Non-crafted legendary weapons were judged from perk combinations, role, tier, investment, and old-vs-new pressure.

## Clean-Slate Prototype Results

Aggregate results from the private prototype:

- Weapons reviewed: 411.
- Crafted weapons preserved: 165.
- Weapon level above 20 preserve/move-on comments: 78.
- Weapon level above 30 hard skip/do-not-demote: 49.
- Exotics preserved: 96.
- Non-crafted legendary weapons clean-slate reviewed: 163.
- Output tags after clean-slate staging: 230 favorite, 151 keep, 30 junk.
- Tag changes staged: 125.

No raw vault CSVs or item-level personal export data should be committed to this repo.

## destiny.report Pass

destiny.report turned out to be especially useful for the old-vs-new question.

The prototype downloaded destiny.report's current public weapon database and matched all weapon hashes from the DIM export.

Useful destiny.report fields included:

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

Aggregate results:

- DIM weapons matched by hash: 411 / 411.
- Crafted weapons skipped: 165.
- Exotics skipped from replacement logic: 83.
- Exact current-modern entries: 94.
- `keep-refarm`: 39.
- `replace-now`: 16.
- `legacy-standalone`: 14.

This supported the product intuition: go hard into new/tiered/updated gear, but keep strong old rolls as bridges until a replacement is actually earned.

## Source Strategy

The proposed source stack is:

1. Bungie manifest/API for canonical data.
2. Current patch notes for sandbox changes.
3. destiny.report for old-vs-new and current weapon metadata.
4. D2Foundry and Clarity-style sources for perk behavior and roll inspection.
5. DIM vault metadata for user-specific context.
6. light.gg, YouTube, Reddit, X, and other community sources as softer meta signal.

## Product Decision

The best distribution for personal and close-friend use is a Codex plugin or skill with a local HTML artifact.

Why:

- No hosted service needed.
- No raw vault data leaves the user's machine unless they explicitly share it.
- Codex can do the source-backed reasoning and file generation.
- The HTML artifact can handle interactive human taste decisions.
- The final output can remain a DIM import CSV.

## Open Questions

- Should the first public-ish version support armor, or start with weapons only?
- Should friend installs use DIM CSV only, or optional Bungie read-only OAuth?
- Should the review artifact export final CSV directly, or hand decisions back to Codex for final generation?
- How much community meta should be cached versus searched fresh each run?
- Should personal preferences live in `decisions.json`, a local profile, or both?
