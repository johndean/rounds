"""
AI MODE prompts — system prompts for the 5 ai_mode variants in UploadView.

Ports MIC's `app/prompts/__init__.py` MIC_TRANSCRIPT_PROMPT + adds the 4
additional modes from IMPLEMENTATION.md §10 (summary / key-moments /
structured-notes / custom-prompt).

`get_prompt_for_mode(mode, custom_prompt=None)` returns the right prompt
string for the given mode. The prompt instructs Gemini to emit:
  - paragraphs separated by blank lines (one per segment)
  - slide markers of form `++<N>*+` on their own line
  - speaker labels of form `**Name:**` inline at start of speech

Also exports `DISCREPANCY_FILTER_PROMPT` used by
`app.engines.llm_client.classify_discrepancies` to label STT-vs-AI diffs
as meaningful (medication / number / name / date / terminology / other)
or noise (filler / punctuation / style).
"""
from __future__ import annotations

from typing import Any, Optional


DISCREPANCY_FILTER_PROMPT = """\
You are auditing word-level diffs between an AI-cleaned medical lecture transcript and a raw Google STT transcript.

For each diff, decide whether the AI transcript's version is a MEANINGFUL mistranscription worth flagging for Medical Review, or NOISE the AI correctly cleaned up.

MEANINGFUL (is_meaningful = true) — flag for review:
- medication  : drug names, brand/generic (e.g., "Narcan" vs "Narcon", "metformin" vs "metoprolol")
- number      : dosages, counts, percentages, vitals (e.g., "500mg" vs "50mg", "12%" vs "20%")
- name        : proper nouns — people, places, institutions (e.g., "Dr. Patel" vs "Dr. Patell")
- date        : dates, years, durations (e.g., "2024" vs "2014")
- terminology : medical/clinical terms where the word itself carries meaning
- other       : any other substantive factual mismatch

NOISE (is_meaningful = false) — the AI correctly cleaned this up:
- filler      : um, uh, er, ah, hm, "you know", "like", "I mean" (AI hard-removes these by design)
- punctuation : commas, periods, quote marks, capitalization
- style       : contractions, word reordering, sentence splitting, false-start cleanup, synonyms that preserve meaning

RULES:
1. Each input item has an `id`, the AI text for the diff range, and the STT text for the diff range.
2. Return a JSON array with ONE object per input item, same `id`, plus `category` (one of the labels above) and `is_meaningful` (boolean).
3. If the only difference is filler words the AI removed, it is NOISE.
4. If the difference involves a medication, number, name, date, or clinical term, it is MEANINGFUL even if small.
5. When genuinely unsure between style and terminology, lean MEANINGFUL — better to over-flag than miss a mistranscription.

OUTPUT: Return ONLY the JSON array. No prose. No markdown fences. No commentary.
"""


_BASE_FORMAT = """\
OUTPUT FORMAT (STRICT):
- Each segment is a paragraph separated by a blank line.
- Slide markers: ++<N>*+ on their own line BEFORE the segment for that slide.
  Sequential 1..N, never skipped, never duplicated.
- Speaker labels: **Name:** inline at the start of speech, FIRST + LAST name only.
  Show only on speaker change. No titles ("Dr.", "DVM", etc.).
- DO NOT add prose around markers. NO commentary outside the transcript itself.

FILLER POLICY:
- Remove acoustic fillers: "um, uh, er, ah, hm, mm".
- Remove discourse fillers ONLY when meaning is preserved:
  "you know, basically, like, right, essentially".
- Keep stutters that carry emphasis. Keep "I mean" / "well" when they introduce a clarification.

VERBATIM RULE:
- Do NOT paraphrase, summarize, reorder, or interpret.
- Preserve drug names, dosages, units exactly as spoken.
- If a word is uncertain, transcribe phonetically — do not omit.
"""


_TRANSCRIPT_PROMPT = f"""\
You are generating a transcript that must be 100% compliant with the
downstream SOP pipeline (medical review → copy edit → CMS → captions → QA).

The output MUST require ZERO manual correction.

CORE EXECUTION RULE:
You are a verbatim transcription system with structural formatting.

{_BASE_FORMAT}
"""


_SUMMARY_PROMPT = f"""\
Produce a condensed summary of the session, structured as a series of
short paragraphs. Each paragraph covers one distinct topic from the talk.

Preserve technical precision (drug names, dosages, anatomical terms).
Cut filler / repetition / chit-chat.

{_BASE_FORMAT}
"""


_KEY_MOMENTS_PROMPT = f"""\
Extract the highest-signal moments from the session. Each segment should
capture one "aha" moment, decision rule, mnemonic, or quotable takeaway
the presenter delivered.

Aim for 8-20 segments per hour of audio. Skip introductions, thanks, and
administrative remarks.

{_BASE_FORMAT}
"""


_STRUCTURED_NOTES_PROMPT = f"""\
Produce outline-style notes organized into sections that match the slide
structure. Within each section, use short paragraphs (not bullet lists).

Preserve the presenter's framing — if they organize by "indications,
contraindications, complications", reflect that ordering. Do not invent
sections the speaker did not introduce.

{_BASE_FORMAT}
"""


_HARDCODED_FALLBACKS = {
    "transcript":       _TRANSCRIPT_PROMPT,
    "summary":          _SUMMARY_PROMPT,
    "key-moments":      _KEY_MOMENTS_PROMPT,
    "structured-notes": _STRUCTURED_NOTES_PROMPT,
}


def get_prompt_for_mode(
    mode: str,
    custom_prompt: Optional[str] = None,
    db_conn: Any = None,
) -> str:
    """
    Return the system prompt for a given ai_mode.

    Resolution order (first hit wins):
      1. mode == 'custom-prompt' AND custom_prompt provided
            → custom_prompt + _BASE_FORMAT
      2. db_conn provided AND prompt_templates has an active row whose
         default_for_mode = mode
            → row.config->>'system_prompt'
      3. hardcoded fallback constants in this module
            → _TRANSCRIPT_PROMPT / _SUMMARY_PROMPT / _KEY_MOMENTS_PROMPT /
              _STRUCTURED_NOTES_PROMPT

    The DB lookup is best-effort: any exception or empty result falls through
    to (3). A DB outage cannot break a Gemini call.

    `mode` is one of: transcript | summary | key-moments | structured-notes
                     | custom-prompt
    `custom_prompt` is only used when mode == 'custom-prompt'.
    `db_conn` is an optional SQLAlchemy sync Connection. Callers in
    app/tasks/ai_process.py already hold one open before this call, so
    passing it here adds a single sub-millisecond SELECT to the upload path
    and unlocks the Settings → Prompt Templates SSOT wiring (migration 049).
    """
    if mode == "custom-prompt" and custom_prompt:
        return custom_prompt + "\n\n" + _BASE_FORMAT

    if db_conn is not None and mode in _HARDCODED_FALLBACKS:
        try:
            from sqlalchemy import text
            row = db_conn.execute(text(
                "SELECT config->>'system_prompt' AS body "
                "  FROM prompt_templates "
                " WHERE default_for_mode = :m "
                "   AND is_active = TRUE "
                " LIMIT 1"
            ), {"m": mode}).first()
            if row and row[0]:
                return row[0]
        except Exception:
            pass  # fall through to hardcoded fallback — never break Gemini

    return _HARDCODED_FALLBACKS.get(mode, _TRANSCRIPT_PROMPT)


def parse_transcript_response(raw: str) -> list[dict]:
    """
    Parse Gemini's transcript response into segment dicts.

    Format expected (per `_BASE_FORMAT`):
      ++<N>*+              <-- slide marker on its own line
      **Speaker Name:** Speech text...
      More speech...

      ++<N+1>*+
      ...

    Returns: list of {text, slide_marker, speaker_name (or None)}.
    Verbatim port of MIC `parse_transcript_response` in
    `app/engines/llm_client.py:431-484`, extended with speaker capture.
    """
    import re

    lines = raw.strip().split("\n")
    segments: list[dict] = []
    current_lines: list[str] = []
    current_slide: Optional[int] = None
    current_speaker: Optional[str] = None

    speaker_rx = re.compile(r"^\*\*(.+?):\*\*\s*(.*)$")

    def _flush() -> None:
        nonlocal current_lines
        if not current_lines:
            return
        text = "\n".join(current_lines).strip()
        if text:
            segments.append({
                "text":          text,
                "slide_marker":  current_slide,
                "speaker_name":  current_speaker,
            })
        current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            _flush()
            continue

        # Slide marker: ++<N>*+
        if stripped.startswith("++") and stripped.endswith("*+"):
            _flush()
            try:
                current_slide = int(stripped[2:-2])
            except ValueError:
                pass
            continue

        # Speaker label: **Name:** rest-of-line
        m = speaker_rx.match(stripped)
        if m:
            _flush()
            current_speaker = m.group(1).strip()
            rest = m.group(2).strip()
            if rest:
                current_lines.append(rest)
            continue

        current_lines.append(line)

    _flush()
    return segments
