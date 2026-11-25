from collections.abc import Iterable

from .audio_file_name import audio_file_name
from .build_pack_zip import PACK_OUTPUTS

# What Start again (J4) may remove or set aside: the record, the line markers and the pack outputs (the same constant
# as the pack, so the two cannot drift), and the `NNN.wav` files of `audio/`. Nothing else, by exact name.
RESTART_FIXED = ("synth_record.json", "line_timings.json", *PACK_OUTPUTS)


def restart_names(project_names: Iterable[str], audio_names: Iterable[str]) -> list[str]:
    """The allowlisted relative names found in two directory listings, the fixed files first and the WAVs last."""
    present = set(project_names)
    wavs = sorted(f"audio/{name}" for name in audio_names if audio_file_name(name))
    return [*(name for name in RESTART_FIXED if name in present), *wavs]
