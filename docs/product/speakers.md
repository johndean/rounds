# Speaker Management

Making sure every segment is attributed to the right person.

> Developer-facing twin: [../specs/speakers.spec.md](../specs/speakers.spec.md)

## What this gives you

**An automatic first pass.** The AI attributes each segment to a speaker as part
of transcription. It is usually close, but the same person can show up under two
names, or a speaker can be missed — so a quick cleanup pass is normal.

**A whole-session speaker list.** Open the Speakers panel (top right of the
Editor, or on the Session Detail page) to see every speaker the system found,
with a name, a role (for example "Instructor"), and an avatar color.

**Rename once, fix everywhere.** Renaming a speaker updates every segment that
references them at once — you do not edit segment by segment.

**Merge duplicates.** When the AI split one person into two, merge them into a
single speaker.

**Reassign a single segment.** If just one segment is attributed wrongly,
reassign it without touching the rest.

**Add a missing speaker.** Create a speaker the AI never detected, then assign
them to the relevant segments.

**Clean exports.** If a segment has no speaker, it exports as **(Unknown)** —
an easy flag to find and fix before publishing.

## Known gaps

- **No re-run of speaker detection from the Editor** — the first pass runs during
  processing; you refine it by hand afterward.
- **No batch reassign** — you cannot select many segments and reassign them all
  at once.
- **No speaker bios or notes.**
- **No cross-session speaker identity** — a speaker named in one session is not
  linked to the same person in another.
