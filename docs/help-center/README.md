# rounds.vin Help Center — content sources

## Files in this directory

- `HELP_CONTENT.ts` — TypeScript export consumed by the in-app help panel
- `faq.md` — operator-readable FAQ (offline reference)
- `articles.md` — long-form articles (where to read about each feature in depth)
- `README.md` — this file

## Relationship to the help-center plan

Reference: `docs/plans/2026-06-05-009-help-center-povin-pixel-port-plan.md`
(active plan, supersedes `-008-`).

`HELP_CONTENT.ts` seeds the in-app panel's **pages** + **faq** tabs. The
structure mirrors po.vin's `HelpPanel.vue` contract.

## Update flow

1. Edit `HELP_CONTENT.ts` directly when copy needs to change.
2. The Phase 3 backend (`help_articles` table, mig 053) will eventually own
   this content; until then, `HELP_CONTENT.ts` is the source of truth.

## Voice rules

- Second person ("you").
- End-user nouns.
- No internal terms (no Vue file names, no SQL table names, no commit SHAs,
  no env vars).
