# Local Decisions And Preferences

This is the main unresolved product design area.

## Current Direction

Keep decision state local. Do not store real vault decisions in Git.

There are probably two different artifacts:

- `decisions.json`: run-specific output from the HTML review artifact. Codex/plugin consumes this to generate the final DIM import CSV.
- `profile.local.json`: durable local preferences, such as how aggressively to prune duplicates, whether to preserve PvP notes, or how to treat holofoils.

The repo can include example schemas and synthetic fixtures, but real user profiles and vault decisions should be ignored.

## Why Split Them?

Run decisions answer "what did I approve for this vault export?"

Durable preferences answer "how do I generally like this auditor to behave?"

Keeping them separate lets the user start clean for a new season without losing taste-level preferences.

## Open Questions

- Should close friends each keep a named local profile?
- Should decisions be portable between machines, or treated as temporary review output?
- Should a future Codex plugin prompt for preference changes before each run?
- How much should old decisions influence new audits when the sandbox changes?
