# Chat and Polls

## What This Does

If the original meeting had a chat log or ran polls, those show up alongside the
transcript so you can anchor them to the moment they happened. Placing a chat
message or a poll pins it to the transcript segment where it belongs, so the
finished session reads in the right order — a question lands next to the line
that prompted it, a poll sits next to the slide it was about.

## Who Can Use It

Anyone signed in who is editing the session can place, move, and remove chat and
poll cards. As with all editing, only the person holding the session can make
changes; in read-only mode the cards are visible but cannot be moved.

## How To Access

Open the session in the Editor. In the right-hand panel, switch to the **Chat**
tab to see the chat messages, or the **Polls** tab to see the polls. Each tab
header shows how many items there are and how many you have placed.

## How To Create

Chat messages and polls are not created here — they are carried over from the
original meeting. What you create is the link between a card and the point in the
transcript where it belongs ("placing" it):

- **Drag a card onto a transcript segment.** Grab the card from the Chat or Polls
  tab and drop it on the segment where it should appear. The card snaps to that
  segment's time and shows a **PLACED** badge with the slide number.
- **Place at the current spot.** With playback at the right moment, click the
  card's **Place at active** (chat) or **Place** (polls) button to anchor it to
  the segment showing then.

## How To Edit

- **Re-anchor a card.** Drag a placed card onto a different segment to move it.
- **Reorder the list.** Hover a card to reveal its grip handle (⇅) and drag it up
  or down to reorder the list.
- **Edit a chat message.** On a *placed* chat message, click **Edit**, change the
  text, and **Save**. (Editing is only available once a chat message is placed.)
- **Polls cannot be edited.** A poll's question, options, and vote counts are
  read-only — they come from the original meeting. You can place, move, and
  remove a poll, but not change its text.

## How To Delete

Click **× Remove** on a placed card to detach it from the transcript. This does
not delete the message or poll — it just unpins it, so it goes back to being
unplaced. You cannot remove the underlying chat or poll content; it stays
available in the tab.

## Common Tasks

- **Pin a key question.** Drag the chat message onto the segment that prompted
  it.
- **Anchor a poll to its slide.** Place the poll on a segment from the slide it
  was about. (Polls from the original meeting are often anchored to their slide
  automatically.)
- **Tidy the order.** Use the grip handles to put the cards in the order they
  happened.
- **Fix a typo in a chat line.** Place the message, then use its Edit button.

## Troubleshooting

- **The Edit button is missing on a chat message.** Editing only appears once a
  message is placed. Place it first, then Edit.
- **I cannot edit a poll.** Polls are read-only by design. You can move or remove
  them, but their text and vote counts come from the meeting and do not change.
- **A card will not drop where I want it.** Drop it directly on a transcript
  segment — that is the only valid target. The grip handle (⇅) is for reordering
  the list, not for placing.
- **My cards will not move.** If you have read-only access, someone else is
  holding the session. Wait for the hold to expire, or ask an admin to
  force-take it.

## FAQs

**Do I have to place every chat message?**
No. Most chat is context only. Place the notable questions and key moments and
leave the rest unplaced.

**Can I change what a chat message or poll says?**
You can edit the text of a *placed chat message*. Polls are read-only — you can
place, move, or remove them, but not change their question, options, or votes.

**What does the PLACED badge mean?**
That the card is anchored to a transcript segment. The badge shows the slide it
landed on. Removing the card clears the badge.

**Why is a poll already anchored when I open the session?**
Polls from the original meeting often arrive already placed on the slide they
belonged to. You can drag them to a different segment if you want.

## Permissions Required

You must be signed in and holding the session's single-editor lock to place,
move, reorder, edit, or remove chat and poll cards. No higher role is required.

## Source Verification
- **Files Used:** frontend/src/components/editor/ChatTab.vue, frontend/src/components/editor/PollsTab.vue, frontend/src/views/EditorView.vue, docs/help-center/articles.md, docs/help-center/faq.md, frontend/src/constants/help-content.ts
- **Components Used:** ChatTab.vue (chat list, drag-to-segment placement, Place at active, × Remove, reorder grip, inline Edit on placed rows), PollsTab.vue (poll cards with option vote bars + winner highlight, drag-to-segment placement, Place / × Remove, reorder grip — no edit), EditorView.vue (Chat / Polls right-rail tabs; handleDropOnSegment / handleRemoveAnchor / handlePlaceAtActive / reorder / handleChatEdit; _inferAnchor poll auto-placement)
- **APIs Used:** GET /v1/sessions/{id}/chat, GET /v1/sessions/{id}/polls, chat/poll anchor placement endpoints (placementsApi.chatAnchor / pollAnchor), chat/poll reorder endpoints (placementsApi.chatReorder / pollsReorder), POST /v1/sessions/{id}/corrections (chat_edit)
- **Database Tables Used:** chat, polls (with poll options), segments, correction_ledger (chat_edit)
- **Permission Logic Used:** JWT presence + single-editor session lock (read-only when not held). No role gate on placement, reorder, or chat edit.
- **Confidence Score:** High — placement drag/drop, Place/Remove buttons, reorder grips, chat-only inline edit, and read-only polls all read directly from ChatTab.vue, PollsTab.vue, and EditorView.vue handlers.
- **Evidence Links:** [frontend/src/components/editor/ChatTab.vue (placement + edit)](../frontend/src/components/editor/ChatTab.vue#L204), [frontend/src/components/editor/PollsTab.vue (place/remove, read-only)](../frontend/src/components/editor/PollsTab.vue#L121), [frontend/src/views/EditorView.vue (handleDropOnSegment / handleChatEdit)](../frontend/src/views/EditorView.vue#L700), [frontend/src/views/EditorView.vue (poll auto-anchor)](../frontend/src/views/EditorView.vue#L158)
