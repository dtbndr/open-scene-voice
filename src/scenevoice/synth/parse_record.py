import re

from scenevoice.synth.accept_alignment import accept_alignment
from scenevoice.synth.alignment import Alignment
from scenevoice.synth.decode_json_document import decode_json_document
from scenevoice.synth.is_text_blank import is_text_blank
from scenevoice.synth.provider_registry import ELEVENLABS, VERTEX, provider_for_model
from scenevoice.synth.record_entry import RecordEntry
from scenevoice.validation import Violation

_RULE = "synth-record"
_MESSAGE = (
    "synth_record.json is not a valid synth record "
    "(delete it to regenerate without a settings check)"
)
_KEYS = frozenset(
    {"ordinal", "sha256", "voice", "model", "language", "instruction", "alignment"}
)
_ALIGNMENT_KEYS = frozenset(
    {"characters", "character_start_times_seconds", "character_end_times_seconds"}
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _entry(item: object, previous: int) -> RecordEntry | None:
    if not isinstance(item, dict) or set(item) != _KEYS:
        return None
    ordinal, sha256, voice, model = (item[k] for k in ("ordinal", "sha256", "voice", "model"))
    language, instruction = item["language"], item["instruction"]
    if type(ordinal) is not int or ordinal < 1 or ordinal <= previous:
        return None
    if not isinstance(sha256, str) or _SHA256.fullmatch(sha256) is None:
        return None
    if not isinstance(voice, str) or is_text_blank(voice):
        return None
    if not isinstance(model, str) or is_text_blank(model):
        return None
    if language is not None and not isinstance(language, str):
        return None
    if instruction is not None and not isinstance(instruction, str):
        return None
    spec = provider_for_model(model)
    alignment: Alignment | None = None
    if spec is VERTEX:
        if item["alignment"] is not None:
            return None
    elif spec is ELEVENLABS:
        raw = item["alignment"]
        if language is not None or instruction is not None:
            return None
        if not isinstance(raw, dict) or set(raw) != _ALIGNMENT_KEYS:
            return None
        accepted = accept_alignment(raw)
        if isinstance(accepted, str):
            return None
        alignment = accepted
    else:
        return None
    return RecordEntry(ordinal, sha256, voice, model, language, instruction, alignment)


def parse_record(data: bytes) -> tuple[RecordEntry, ...] | Violation:
    """Strictly parse synth_record.json entries (Gemini and ElevenLabs); never raises, never repairs."""
    malformed = Violation(_RULE, _MESSAGE, line=None)
    document = decode_json_document(data)
    if isinstance(document, Violation):
        return malformed
    if not isinstance(document, dict) or set(document) != {"scenes"}:
        return malformed
    scenes = document["scenes"]
    if not isinstance(scenes, list):
        return malformed
    entries: list[RecordEntry] = []
    previous = 0
    for item in scenes:
        entry = _entry(item, previous)
        if entry is None:
            return malformed
        entries.append(entry)
        previous = entry.ordinal
    return tuple(entries)
