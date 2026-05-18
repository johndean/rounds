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
"""
from __future__ import annotations

from typing import Optional


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


def get_prompt_for_mode(mode: str, custom_prompt: Optional[str] = None) -> str:
    """
    Return the system prompt for a given ai_mode.

    `mode` is one of: transcript | summary | key-moments | structured-notes
                     | custom-prompt
    `custom_prompt` is only used when mode == 'custom-prompt'.
    """
    if mode == "custom-prompt" and custom_prompt:
        return custom_prompt + "\n\n" + _BASE_FORMAT
    return {
        "transcript":       _TRANSCRIPT_PROMPT,
        "summary":          _SUMMARY_PROMPT,
        "key-moments":      _KEY_MOMENTS_PROMPT,
        "structured-notes": _STRUCTURED_NOTES_PROMPT,
    }.get(mode, _TRANSCRIPT_PROMPT)


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
