from collections.abc import Sequence
from pathlib import Path

from scenevoice.synth.audio_dir import AUDIO_DIR
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.wav_name import wav_name


def final_ok_text(scenes: Sequence[PlanScene], scene: int | None, out_dir: str | Path) -> str:
    """Final success line (after the prefix): full run counts scenes, scene mode names the file."""
    if scene is None:
        return f"OK {len(scenes)} scenes written to {out_dir}"
    return f"OK scene {scene} written to {Path(out_dir) / AUDIO_DIR / wav_name(scene)}"
