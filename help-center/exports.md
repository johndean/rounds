# Exporting and downloading a transcript

## What This Does

When a transcript is ready to leave the app, you export it to a file. The editor's Download menu turns the current transcript into the format the next step needs:

- **Word (.docx)** — a Word document with each speaker's name in bold and a heading for each slide. This is the macro-compatible format used for the CMS prep workflow.
- **Captions (.srt)** — a SubRip caption file for the video player. Structural markup such as slide markers and speaker labels is stripped out so the captions read as plain on-screen speech.
- **Plain Text (.txt)** — a quick, unformatted copy for pasting into an email or note.
- **Word Macro (.zip)** — a bundle containing the Word doc, the caption files, plain text, an HTML version, and a slide outline, all in one download. Use this when you need several formats at once.

Every download is generated fresh from the current state of the transcript at the moment you click, so it always reflects your latest edits and speaker fixes.

## Who Can Use It

Anyone signed in who can open a session in the editor can download its exports. There is no separate export permission.

## How To Access

1. Open the session in the editor.
2. Click the **Download** button in the editor toolbar.
3. A short menu drops down with the four formats.

The menu closes if you click anywhere outside it.

## How To Create

"Creating" an export is the act of downloading one:

1. Open the **Download** menu in the editor.
2. Click the format you want.
3. A brief "Preparing…" notice appears while the file is built, then your browser's save dialog opens. Pick where to save it.

You do not need to prepare or queue anything ahead of time — the file is built on the spot from the live transcript.

## How To Edit

You do not edit an export file inside the app. An export is a snapshot, not a living document. To change what an export contains, edit the transcript itself — fix the text, correct the speakers, place the chat and polls — and then download again. The next download reflects your changes immediately, because each download is regenerated from scratch.

If you opened the file in Word, a text editor, or a captioning tool, any further edits happen in that tool, not in the app.

## How To Delete

There is nothing to delete inside the app. An export is a file your browser saved to your computer or shared drive — delete it there the way you would delete any downloaded file. The app keeps no copy you need to clean up, and re-downloading is always free since the file is rebuilt each time.

## Common Tasks

- **Get a clean Word document for CMS prep.** Open Download and pick **Word (.docx)**. Speaker names come through in bold with a heading per slide.
- **Get captions for the video player.** Pick **Captions (.srt)**. The caption text is cleaned of slide markers and speaker labels so it reads as plain speech.
- **Grab a quick plain-text copy.** Pick **Plain Text (.txt)** for pasting into email or notes.
- **Get everything in one download.** Pick **Word Macro (.zip)** for the full bundle — Word, captions, plain text, HTML, and a slide outline together.
- **Refresh an export after edits.** Just download again. The new file includes every change since your last download.

## Troubleshooting

- **The download did not start.** You will see an error notice with the reason. The most common cause is that the session is not finished processing yet — make sure its status is ready, then try again.
- **A speaker shows as "(Unknown)".** That segment has no speaker assigned. Open the session, assign the correct speaker in the Speakers panel, and download again.
- **Filler words like "um" and "uh" are missing.** That is expected. Fillers are removed when the transcript is first cleaned up, according to the prompt template chosen at upload, so they are gone from every format you export.
- **A caption line looks like plain speech with no slide or speaker tags.** Also expected. The caption format deliberately strips that structural markup so the on-screen text is just the words spoken.
- **I want a format I do not see in the menu.** The editor menu offers Word, Captions, Plain Text, and the Word Macro bundle. The bundle's contents cover the common needs (it includes an HTML version and a standalone caption file inside the zip).

## FAQs

**Where do exports come from?**
The Download menu in the editor generates the file fresh from the current transcript every time you click. There is no stale cached copy.

**Do I have to re-export after I make an edit?**
Yes, if you want the change in the file. Each download is a snapshot of the transcript at that moment, so download again after editing.

**What is in the Word Macro zip?**
A Word document, a caption file, a plain-text file, an HTML version, and a slide outline — bundled together so you can grab all the formats in a single download.

**Why are the captions missing speaker names?**
Caption files are meant to show only the spoken words on screen, so slide markers and speaker labels are stripped out of the caption format.

## Permissions Required

Any signed-in user who can open a session in the editor can download its exports. There is no admin-only restriction on downloading.

---

## Source Verification
- **Files Used:** [frontend/src/components/editor/DownloadMenu.vue](../frontend/src/components/editor/DownloadMenu.vue), [app/api/exports.py](../app/api/exports.py), [app/engines/artifact_transformer.py](../app/engines/artifact_transformer.py), [app/iil/normalization.py](../app/iil/normalization.py), [frontend/src/services/api.ts](../frontend/src/services/api.ts), [frontend/src/constants/help-content.ts](../frontend/src/constants/help-content.ts), [docs/product/exports-artifacts-product-spec.md](../docs/product/exports-artifacts-product-spec.md), [docs/help-center/articles.md](../docs/help-center/articles.md)
- **Components Used:** DownloadMenu.vue (Download button in EditorView.vue)
- **APIs Used:** `GET /v1/sessions/{session_id}/exports/{format}` ([app/api/exports.py:41](../app/api/exports.py#L41)); `GET /v1/sessions/{session_id}/captions.vtt` (in-editor caption track, ETag-cached — [app/api/exports.py:120](../app/api/exports.py#L120))
- **Database Tables Used:** `sessions`, `segments`, `slides`, `speakers`, `bullets`, `chat_messages`, `session_slide_resources` (read by `load_session_for_export` — [app/engines/artifact_transformer.py:545](../app/engines/artifact_transformer.py#L545)); `artifacts` (best-effort metadata write — [app/api/exports.py:84](../app/api/exports.py#L84)); `correction_ledger` (caption ETag fingerprint — [app/api/exports.py:138](../app/api/exports.py#L138))
- **Permission Logic Used:** JWT presence only (`CurrentUser`/`_user` on export and captions endpoints; no admin gate, no role check)
- **Confidence Score:** High — verified the four menu formats, the per-format rendering, the "(Unknown)" speaker fallback, and that filler removal happens at normalization (not per-format) directly in code.
- **Evidence Links:** [DownloadMenu.vue:27-32](../frontend/src/components/editor/DownloadMenu.vue#L27) (4 menu formats: docx/srt/txt/zip), [exports.py:31-38](../app/api/exports.py#L31) (backend also supports vtt/html, not in the menu), [artifact_transformer.py:236-275](../app/engines/artifact_transformer.py#L236) (SRT strips structural markup), [artifact_transformer.py:153-205](../app/engines/artifact_transformer.py#L153) (docx bold speaker names), [normalization.py:40](../app/iil/normalization.py#L40) (TIER1_WORDS fillers removed at normalize phase), [artifact_transformer.py:523-539](../app/engines/artifact_transformer.py#L523) (zip bundle contents)
