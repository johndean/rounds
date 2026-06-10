# Speakers

## What This Does

Every segment of a transcript is attributed to a speaker. The system takes a
first pass at who is talking, but that pass often needs cleanup — names come
through wrong, or one person ends up split under two labels. The speaker tools
let you fix the roster for the whole session and reattribute individual segments,
so the finished transcript credits the right person throughout.

## Who Can Use It

Anyone signed in who is editing the session can manage speakers. As with all
editing, only the person holding the session can make changes — if you are in
read-only mode, the speaker controls are unavailable until the hold expires.

## How To Access

Open the session in the Editor. The speaker roster lives in the right-hand panel
under the **Admin** tab, in a card titled **Speakers**. To change who said one
particular line, you do that on the segment itself in the transcript, using its
**Speaker** button.

## How To Create

To add a speaker the system missed:

1. In the Speakers card, click **Add speaker**.
2. Type the person's name and press Enter (or click **Add**). The new speaker is
   created with the Speaker role.
3. Change the role to Moderator afterward if needed by clicking the role pill on
   the new card.

## How To Edit

In the **Speakers** card:

- **Rename a speaker.** Click the name, type the correction, and click away or
  press Enter. The new name applies everywhere that speaker appears.
- **Change a role.** Click the role pill on a speaker's card to toggle between
  **Moderator** and **Speaker**.

On a transcript segment:

- **Reassign one segment to a different speaker.** Click the segment's
  **Speaker** button and pick the right person from the tiles. This changes just
  that segment.

## How To Delete

In the Speakers card, click the **×** on a speaker's card to remove them. You are
asked to confirm first. Removing a speaker takes them out of the roster for this
session.

If the system split one real person into two speakers, fix it by renaming both to
the correct name (or reattributing the misfiled segments with the per-segment
**Speaker** button), then removing the leftover duplicate. There is no one-click
"merge two speakers" action — you consolidate by renaming or reassigning and then
removing the extra.

## Common Tasks

- **Fix a wrong name.** Rename the speaker in the Speakers card; every segment
  updates at once.
- **Consolidate a duplicate.** Reassign the misfiled segments to the correct
  speaker, then remove the duplicate from the roster.
- **Mark the moderator.** Click the role pill on the right person's card so it
  reads Moderator.
- **Credit a missed speaker.** Add them in the Speakers card, then use each
  segment's Speaker button to attribute their lines.

## Troubleshooting

- **A segment shows "(Unknown)" in my download.** That segment has no speaker
  assigned. Open the session, use the segment's Speaker button to assign the
  right person, and download again.
- **The same person appears twice.** Reattribute the affected segments to one of
  the two, then remove the other from the roster.
- **The name will not save.** A blank name is rejected — type a name and try
  again. If you are in read-only mode, the controls are disabled until the
  session's hold expires.
- **My speaker controls are greyed out.** Someone else is holding the session.
  Wait for the hold to expire, or ask an admin to force-take it.

## FAQs

**Does renaming a speaker fix every segment at once?**
Yes. A rename in the Speakers card applies to every segment that references that
speaker, so it is usually a one-time fix done early in editing.

**Can I merge two speakers in one step?**
No single "merge" button exists. Reassign the misfiled segments to the speaker
you want to keep, then remove the duplicate from the roster.

**What roles can a speaker have?**
Moderator or Speaker. Click the role pill on a speaker's card to switch.

**A segment is credited to the wrong person — do I have to fix the whole
roster?**
No. Use that one segment's Speaker button to reassign just that line.

## Permissions Required

You must be signed in and holding the session's single-editor lock to add,
rename, reassign, or remove speakers. No higher role is required — these are
standard editing actions for whoever holds the session.

## Source Verification
- **Files Used:** frontend/src/components/editor/SpeakerEditPanel.vue, frontend/src/components/editor/TranscriptPane.vue, frontend/src/views/EditorView.vue, frontend/src/services/api.ts (speakers), docs/help-center/articles.md, docs/help-center/faq.md, frontend/src/constants/help-content.ts
- **Components Used:** SpeakerEditPanel.vue (roster card — inline rename, role toggle, Add speaker, remove ×), TranscriptPane.vue (per-segment Speaker picker), EditorView.vue (mounts SpeakerEditPanel under the Admin right-rail tab; onReassignSpeakerLive handler)
- **APIs Used:** GET /v1/sessions/{id}/speakers, POST /v1/sessions/{id}/speakers (add), PATCH /v1/sessions/{id}/speakers/{speakerId} (rename / role), DELETE /v1/sessions/{id}/speakers/{speakerId} (remove), POST /v1/sessions/{id}/segments/{segmentId}/speaker-reassign (per-segment)
- **Database Tables Used:** session_speakers, segments
- **Permission Logic Used:** JWT presence + single-editor session lock (read-only when not held). No role gate on speaker CRUD.
- **Confidence Score:** High — every speaker action (rename, role toggle, add, remove, per-segment reassign) maps to a confirmed component handler and api.ts endpoint; absence of a merge-speaker endpoint verified in api.ts.
- **Evidence Links:** [frontend/src/components/editor/SpeakerEditPanel.vue (rename/role/add/remove)](../frontend/src/components/editor/SpeakerEditPanel.vue#L51), [frontend/src/components/editor/TranscriptPane.vue (Speaker button)](../frontend/src/components/editor/TranscriptPane.vue#L490), [frontend/src/services/api.ts (speakers, no merge)](../frontend/src/services/api.ts#L310), [frontend/src/views/EditorView.vue (onReassignSpeakerLive)](../frontend/src/views/EditorView.vue#L994)

> Maintainer note: the seed articles.md says you can "Merge two speakers." There
> is no merge-speaker endpoint in api.ts (the only `merge` correction type is for
> segments, not speakers). This article describes consolidation via rename /
> per-segment reassign + remove instead. IMPLEMENTATION NOT FOUND: one-click
> speaker merge.
