from collections.abc import Callable, Sequence
from pathlib import Path

from scenevoice.synth.audio_dir import AUDIO_DIR
from scenevoice.synth.audio_rel_path import audio_rel_path
from scenevoice.synth.neighbour_texts import neighbour_texts
from scenevoice.synth.plan_scene import PlanScene
from scenevoice.synth.provider import (
    Provider,
    ProviderAudio,
    ProviderError,
    ProviderRequest,
)
from scenevoice.synth.validate_audio import validate_audio
from scenevoice.synth.write_wav import write_wav


def synth_scenes(
    scenes: Sequence[PlanScene],
    instruction: str | None,
    voice: str,
    language: str | None,
    out_dir: str | Path,
    provider: Provider,
    progress: Callable[[str], None],
    total: int | None = None,
    *,
    plan: Sequence[PlanScene],
    record_hook: Callable[[int, ProviderAudio], str | None] | None = None,
) -> str | None:
    """Synthesize scenes in plan order; stop at the first failure (written WAVs are kept).

    `out_dir` is DIR; the WAVs are written into `DIR/audio`.
    `plan` is every plan scene; it supplies each request's neighbouring bodies (`scenes` may hold one).
    `total` is the plan scene count shown in progress (default: len(scenes)).
    `record_hook(ordinal, audio)` runs after the WAV is at its final name and before that scene's
    progress line; a returned message stops the run as `scene N: <message>` (that WAV is kept).
    Returns None on success or a raw failure message (redaction is the caller's job).
    """
    write_dir = Path(out_dir) / AUDIO_DIR
    if total is None:
        total = len(scenes)
    for scene in scenes:
        try:
            previous_text, next_text = neighbour_texts(plan, scene.ordinal)
            request = ProviderRequest(scene.body, previous_text, next_text, voice, language, instruction)
            audio = provider(request)
        except ProviderError as error:
            return f"scene {scene.ordinal}: {error}"
        bad = validate_audio(audio) or write_wav(write_dir, scene.ordinal, audio.wav)
        if bad is not None:
            return f"scene {scene.ordinal}: {bad.message}"
        if record_hook is not None:
            hooked = record_hook(scene.ordinal, audio)
            if hooked is not None:
                return f"scene {scene.ordinal}: {hooked}"
        progress(f"scene {scene.ordinal}/{total} written to {audio_rel_path(scene.ordinal)}")
    return None
