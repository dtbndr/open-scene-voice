from scenevoice.pack.format_duration import format_duration
from scenevoice.synth import PlanScene, audio_rel_path

_HEADER = "scene,label,file,duration_s\n"


def _field(text: str) -> str:
    if any(c in text for c in ',"\n\r'):
        return '"' + text.replace('"', '""') + '"'
    return text


def build_manifest(scenes: list[PlanScene], frames: list[int]) -> bytes:
    rows = [_HEADER]
    for scene, count in zip(scenes, frames, strict=True):
        fields = [
            str(scene.ordinal),
            scene.title,
            audio_rel_path(scene.ordinal),
            format_duration(count),
        ]
        rows.append(",".join(_field(f) for f in fields) + "\n")
    return "".join(rows).encode("utf-8")
