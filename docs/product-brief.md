# Product Brief

## Working Name

Destiny Vault Auditor

## One-Liner

A local-first Codex plugin that audits a Destiny 2 vault, explains what to keep, junk, or refarm, and generates a review artifact plus a DIM import CSV.

## Problem

Destiny 2 vault cleanup is hard because the correct answer is not just "what is a god roll?" A good audit has to combine:

- Current sandbox and patch notes.
- Actual vault contents.
- Crafted and high-investment exceptions.
- Old vs new same-name weapon pressure.
- PvE, PvP, build, and sentimental roles.
- Whether a replacement is currently farmable.

Existing tools are excellent at parts of this. DIM is the vault UI. destiny.report and D2Foundry are great for current weapon data. light.gg and creators are useful for meta signal. The missing piece is a personal, explainable decision layer that can say why each item should stay, go, or be refarmed.

The tool should avoid choice paralysis. It can use many signals internally, but the default experience should be a small set of clear buckets with short explanations and expandable evidence.

## Target Users

- Primary: the repo owner and close friends.
- Secondary: advanced Destiny players who already use DIM and understand that tags are recommendations, not deletion commands.
- Not initially for: a broad public audience that expects hosted OAuth, account support, and polished onboarding.

## MVP Workflow

1. User exports weapons and armor CSVs from DIM.
2. Codex/plugin loads the CSVs and public source data.
3. The audit engine scores each item.
4. The plugin writes:
   - `audit-summary.md`
   - `vault-review.html`
   - `decisions.json`
5. The user reviews edge cases in the HTML artifact and exports reviewed decisions.
6. Codex/plugin consumes the reviewed decisions and writes the final `dim-import.csv`.
7. The user imports the final CSV into DIM manually.

The MVP input mode is DIM CSV only. Bungie OAuth and browser automation are out of the core path.

## Non-Goals For MVP

- No dismantling, equipping, locking, unlocking, or transferring items.
- No direct DIM Sync writes.
- No Bungie OAuth requirement.
- No hosted account service.
- No raw vault CSV uploads to a third-party server.
- No permanent storage of OAuth tokens.

## Success Criteria

- Every recommendation has a clear reason.
- The user can see the blast radius before any DIM import.
- The tool distinguishes "junk now" from "keep until refarmed."
- The tool protects crafted, high-level, exotic, and personally annotated items by default.
- Weapons and armor are both represented in the same review flow.
- Advanced signals such as locked state, low power level, wishlists, kill trackers, and community meta improve confidence without becoming required manual choices.
- The generated HTML artifact makes edge-case review faster than editing a spreadsheet.

## Product Tone

Quietly opinionated, not bossy. The tool should feel like a good Destiny friend who knows the patch notes and says, "this roll is fine, but the new tiered version exists, so use it as a bridge."
