from typing import Any

from scenevoice.pack.clip_frames import clip_frames
from scenevoice.pack.time_range import time_range
from scenevoice.pack.timeline_constants import FRAME_RATE, SAMPLE_RATE
from scenevoice.synth import PlanScene, audio_rel_path


def clip_entry(scene: PlanScene, wav_frames: int) -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "Clip.1",
        "metadata": {},
        "name": f"Scene {scene.ordinal}",
        "source_range": time_range(0, clip_frames(wav_frames), FRAME_RATE),
        "effects": [],
        "markers": [],
        "media_reference": {
            "OTIO_SCHEMA": "ExternalReference.1",
            "metadata": {},
            "name": "",
            "available_range": time_range(0, wav_frames, SAMPLE_RATE),
            "target_url": audio_rel_path(scene.ordinal),
        },
    }
