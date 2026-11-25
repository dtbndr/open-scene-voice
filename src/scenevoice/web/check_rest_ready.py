from .audio_scan import AudioScan
from .common_settings import common_settings
from .planned_scene import PlannedScene
from .record_read import RecordRead
from .text_witness import text_witness
from .timings_read import TimingsRead

NOTHING_VOICED = "Nothing has been voiced yet."
MISMATCH = "What was voiced does not match this script or these settings. Choose Start again."


def check_rest_ready(
    scenes: tuple[PlannedScene, ...], audio: AudioScan, record: RecordRead, timings: TimingsRead
) -> str | None:
    """The J12 refusal message when "voice the rest" cannot safely continue what is on disk, else None.

    The ONE implementation of the seven refusals (J3): nothing voiced or no `audio/` folder (use all); a voiced scene
    with no record or no entry; entries that disagree on voice, model, language or instruction; a WAV or record
    ordinal outside the plan; a record sha256 that differs from its WAV's; a false text witness (J10).
    """
    voiced = audio.hashes
    if not voiced:
        return NOTHING_VOICED
    if record.state != "ok":
        return MISMATCH
    entries = {item.ordinal: item for item in record.items}
    if any(ordinal not in entries for ordinal in voiced):
        return MISMATCH
    if common_settings(record.items) is None:
        return MISMATCH
    planned = {scene.ordinal for scene in scenes}
    if not set(voiced) <= planned or not set(entries) <= planned:
        return MISMATCH
    for scene in scenes:
        if scene.ordinal not in voiced:
            continue
        item = entries[scene.ordinal]
        if item.sha256 != voiced[scene.ordinal]:
            return MISMATCH
        if text_witness(scene, item, voiced[scene.ordinal], timings) is False:
            return MISMATCH
    return None
