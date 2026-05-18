"""
Chat transcript parser.

Verbatim port of MIC `app/engines/chat_parser.py` (196 LOC). Supports the
two Zoom/webinar chat export formats:

  Format 1 (simple):  HH:MM:SS\\tSpeaker:\\tMessage
  Format 2 (verbose): YYYY-MM-DD HH:MM:SS From Speaker to Recipient:\\n\\tMessage

Auto-detects from the first line. DMs labeled `is_private=True` but not
excluded. Never raises — returns [] on any parse failure.

Closes audit gap 🔴 #14. Phase 6f / U96.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def parse_chat_file(content: str, start_time_override: Optional[str] = None) -> list[dict]:
    """
    Parse chat .txt content. Auto-detects format.
    `start_time_override` (ISO datetime) overrides Format 2's auto-detect.
    Returns: list of {timestamp, speaker, recipient, message, is_private, is_reply, reply_context}
    """
    lines = content.strip().split("\n")
    if not lines:
        return []
    first = lines[0].strip()
    if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} From ", first):
        return _parse_format2(lines, start_time_override)
    if re.match(r"^\d{2}:\d{2}:\d{2}\t", first):
        return _parse_format1(lines)
    logger.warning(f"chat_parser: unrecognized format — first line: {first[:80]!r}")
    return []


def _parse_format1(lines: list[str]) -> list[dict]:
    messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        timestamp_str = parts[0].strip()
        speaker = parts[1].strip().rstrip(":")
        message = "\t".join(parts[2:]).strip()
        timestamp = _parse_hms(timestamp_str)
        if timestamp is None:
            continue
        is_reply = message.startswith("Replying to ")
        reply_context = None
        if is_reply:
            m = re.match(r'Replying to "(.+?)"\s*\n?(.*)', message, re.DOTALL)
            if m:
                reply_context = m.group(1)
                message = m.group(2).strip() or message
        messages.append({
            "timestamp":     timestamp,
            "speaker":       speaker,
            "recipient":     "Everyone",
            "message":       message,
            "is_private":    False,
            "is_reply":      is_reply,
            "reply_context": reply_context,
        })
    logger.info(f"chat_parser[fmt1]: parsed {len(messages)} messages")
    return messages


def _parse_format2(lines: list[str], start_time_override: Optional[str] = None) -> list[dict]:
    header_re = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) From (.+?) to (.+?):\s*$")
    blocks: list[dict] = []
    current: Optional[dict] = None
    for line in lines:
        match = header_re.match(line)
        if match:
            if current:
                blocks.append(current)
            current = {
                "datetime_str":  match.group(1),
                "speaker":       match.group(2).strip(),
                "recipient_raw": match.group(3).strip(),
                "lines":         [],
            }
        elif current is not None:
            stripped = line.lstrip("\t")
            if stripped:
                current["lines"].append(stripped)
    if current:
        blocks.append(current)
    if not blocks:
        return []

    start_dt = None
    if start_time_override:
        try:
            start_dt = datetime.fromisoformat(start_time_override)
        except ValueError:
            logger.warning("chat_parser: invalid start_time_override")
    if start_dt is None:
        for b in blocks:
            r = b["recipient_raw"].lower()
            if "everyone" in r and "(direct message)" not in r:
                try:
                    start_dt = datetime.strptime(b["datetime_str"], "%Y-%m-%d %H:%M:%S")
                    break
                except ValueError:
                    continue
    if start_dt is None and blocks:
        try:
            start_dt = datetime.strptime(blocks[0]["datetime_str"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return []

    messages = []
    for b in blocks:
        try:
            msg_dt = datetime.strptime(b["datetime_str"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        timestamp = max(0.0, (msg_dt - start_dt).total_seconds())
        message = "\n".join(b["lines"]).strip()
        if not message:
            continue
        recipient_raw = b["recipient_raw"]
        is_private = "(direct message)" in recipient_raw.lower()
        recipient = re.sub(r"\s*\(direct message\)\s*", "", recipient_raw).strip()
        is_reply = message.startswith("Replying to ")
        reply_context = None
        if is_reply:
            m = re.match(r'Replying to "(.+?)":\s*\n?(.*)', message, re.DOTALL)
            if m:
                reply_context = m.group(1)
                remaining = m.group(2).strip()
                if remaining:
                    message = remaining
        messages.append({
            "timestamp":     round(timestamp, 1),
            "speaker":       b["speaker"],
            "recipient":     recipient,
            "message":       message,
            "is_private":    is_private,
            "is_reply":      is_reply,
            "reply_context": reply_context,
        })
    logger.info(f"chat_parser[fmt2]: parsed {len(messages)} messages")
    return messages


def _parse_hms(s: str) -> Optional[float]:
    m = re.match(r"(\d{1,2}):(\d{2}):(\d{2})", s)
    if not m:
        return None
    h, mins, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return h * 3600 + mins * 60 + sec
