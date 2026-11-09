import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path

from scenevoice.synth.provider import ProviderAudio
from scenevoice.synth.record_entry import RecordEntry
from scenevoice.synth.record_name import RECORD_NAME
from scenevoice.synth.record_settings import RecordSettings
from scenevoice.synth.serialize_record import serialize_record
from scenevoice.synth.write_record_file import write_record_file


def make_record_hook(
    out_dir: str | Path,
    settings: RecordSettings,
    entries: Sequence[RecordEntry],
) -> Callable[[int, ProviderAudio], str | None]:
    """Build the post-WAV hook that rewrites synth_record.json after each scene.

    Entries are held in memory (seeded from `entries`), keyed by ordinal and written in
    ascending order; the record file is never re-read. The hook returns None or the failure message.
    """
    held = {entry.ordinal: entry for entry in entries}
    directory = Path(out_dir)

    def hook(ordinal: int, audio: ProviderAudio) -> str | None:
        held[ordinal] = RecordEntry(
            ordinal=ordinal,
            sha256=hashlib.sha256(audio.wav).hexdigest(),
            voice=settings.voice,
            model=settings.model,
            language=settings.language,
            instruction=settings.instruction,
            alignment=audio.alignment,
        )
        try:
            data = serialize_record([held[key] for key in sorted(held)])
        except UnicodeEncodeError:  # an alignment character with no UTF-8 form (D21)
            return f"could not write {RECORD_NAME}"
        return write_record_file(directory, data)

    return hook
