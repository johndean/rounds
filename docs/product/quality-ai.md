# Quality & AI Accuracy

How the system tells you where the AI was unsure — so you can spend your review
time where it matters.

> Developer-facing twin: [../specs/quality-ai.spec.md](../specs/quality-ai.spec.md)

## What this gives you

**A confidence score on every segment.** As it transcribes, the AI records how
confident it was. Low-confidence segments are surfaced for review rather than
buried in the transcript.

**The Discrepancies view.** This lists the segments where the AI transcript
diverges from the reference, sorted so the riskiest ones come first. For each
segment you can:

- **Mark OK** — confirm the AI got it right and clear the flag.
- **Edit** — fix the text.
- **Dismiss** — skip it without changing anything.

You do not have to clear every flag. Work down the list in priority order; once
the genuinely shaky segments are handled, the rest can move to the next reviewer.

**Accuracy flags.** Segments are tagged to point you at what to check:

- **Low confidence** — the AI's certainty was below the review threshold.
- **Drift** — the segment diverges from the slide reference.
- **Uncertain** — the model flagged its own output as shaky.
- Content flags — **Medication, Name, Number, Date, Terminology** — that mark
  spots worth a careful second look.

**Priority ordering you can trust.** The review queue is ordered by a consistent
scoring rule — the lowest-confidence and most-flagged segments rise to the top —
so the first items you see are the ones most likely to need a human.

**Two transcription engines.** AI Mode (Gemini) produces the richer transcript;
Default Mode uses standard cloud transcription. The system routes classification
work to the appropriate engine behind the scenes.

## Known gaps

- **You cannot manually adjust a segment's confidence score** — you confirm or
  edit, but the number itself is the AI's.
- **No accuracy trends over time** — you see this session's flags, not whether
  accuracy is improving across sessions.
- **No per-flag statistics** — there is no dashboard of "how many Medication
  flags this week."
- **Corrections do not retrain the model** — your edits are captured for the
  audit trail and for the Improvements patterns, but they do not feed back into
  the transcription engine directly.
