# Configuration UX

The auditor should feel like a pre-flight check, not a settings screen.

## Default Flow

1. User provides DIM weapon and armor CSVs.
2. Auditor shows source freshness and the selected audit posture.
3. User chooses a small cleanup mode.
4. Auditor runs and generates review queues.
5. User resolves edge cases in the HTML artifact.
6. Codex/plugin consumes reviewed decisions and writes the DIM import CSV.

## Light Config Surface

Expose only a small set of posture controls:

- Cleanup mode: `gentle`, `clean-slate`, `aggressive`.
- High investment threshold: default level `30+` hard protect, level `21-30` investment comment.
- Locked item behavior: `protect`, `review`, `ignore`.
- Duplicate pruning: `keep-more`, `balanced`, `prune-hard`.
- Old-vs-new pressure: `keep-bridges`, `balanced`, `prefer-new`.
- PvP caution: `cautious`, `balanced`, `strict`.
- Low-power threshold: optional note-only signal.

## Avoiding Choice Paralysis

Most signals should stay internal:

- Locked state.
- Low power/light level.
- Current DIM tag.
- Wishlist matches.
- Kill trackers.
- Holofoil or cosmetic rarity.
- Loadout membership.
- Source disagreement.

The UI should show these as explanation chips on each item, not as required choices before every audit.

## Default Recommendation

Use `clean-slate`, `locked-behavior=review`, `old-vs-new=balanced`, `duplicate-pruning=balanced`, and `pvp-caution=balanced` for the repo owner's Monument of Triumph-style cleanup.
