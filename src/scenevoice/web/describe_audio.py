from .audio_scan import AudioScan
from .common_settings import common_settings
from .planned_scene import PlannedScene
from .record_read import RecordRead
from .text_witness import text_witness
from .timings_read import TimingsRead


def describe_audio(scenes: tuple[PlannedScene, ...], audio: AudioScan, record: RecordRead, timings: TimingsRead) -> dict[str, object]:
    """The `audio` object of the project detail: per plan scene voiced, recorded, WAV-matches-record and text witness."""
    entries = {item.ordinal: item for item in record.items}
    rows = []
    for scene in scenes:
        ordinal = scene.ordinal
        voiced = ordinal in audio.hashes
        item = entries.get(ordinal)
        rows.append(
            {
                "ordinal": ordinal,
                "voiced": voiced,
                "recorded": item is not None,
                "wav_matches_record": item.sha256 == audio.hashes[ordinal] if voiced and item is not None else None,
                "text_matches": text_witness(scene, item, audio.hashes[ordinal], timings) if voiced else None,
            }
        )
    planned = {scene.ordinal for scene in scenes}
    return {
        "scenes": rows,
        "extra_ordinals": sorted((set(audio.named) | set(entries)) - planned),
        "record": record.state,
        "settings": common_settings(record.items),
    }
