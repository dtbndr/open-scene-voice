"""Contract-valid synth_record.json fixtures for align routing tests (no provider call).

Entries are plain dicts that parse_record accepts: non-blank voice, 64 lowercase hex sha256,
ElevenLabs eleven_flash_v2_5 with null language and instruction and a non-empty alignment of three
equal-length arrays, Gemini gemini-3.8-flash-tts with null alignment. Pass entries to write_record in
strictly increasing ordinal order.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

RECORD_FILE = "synth_record.json"


def sha_of(wav: bytes) -> str:
    return hashlib.sha256(wav).hexdigest()


def per_char_alignment(text: str, step: float = 0.1) -> dict[str, Any]:
    """One element per character of text, the start of character i being i * step."""
    starts = [i * step for i in range(len(text))]
    return {
        "characters": list(text),
        "character_start_times_seconds": starts,
        "character_end_times_seconds": [s + step for s in starts],
    }


def eleven_entry(
    ordinal: int,
    wav: bytes,
    text: str,
    *,
    sha256: str | None = None,
    alignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """ElevenLabs entry; sha256 defaults to the hash of wav, alignment to per_char_alignment(text)."""
    return {
        "ordinal": ordinal,
        "sha256": sha256 if sha256 is not None else sha_of(wav),
        "voice": "voice-id",
        "model": "eleven_flash_v2_5",
        "language": None,
        "instruction": None,
        "alignment": alignment if alignment is not None else per_char_alignment(text),
    }


def gemini_entry(
    ordinal: int, wav: bytes, *, sha256: str | None = None
) -> dict[str, Any]:
    """Gemini entry (alignment null); sha256 defaults to the hash of wav."""
    return {
        "ordinal": ordinal,
        "sha256": sha256 if sha256 is not None else sha_of(wav),
        "voice": "Leda",
        "model": "gemini-3.8-flash-tts",
        "language": "en-GB",
        "instruction": None,
        "alignment": None,
    }


def write_record(directory: Path, *entries: dict[str, Any]) -> Path:
    """Write DIR/synth_record.json holding the entries in the given order."""
    path = directory / RECORD_FILE
    path.write_text(json.dumps({"scenes": list(entries)}), encoding="utf-8")
    return path
