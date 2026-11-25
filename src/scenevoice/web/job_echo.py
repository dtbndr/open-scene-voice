from .planned_scene import PlannedScene
from .script_revision import script_revision


def job_echo(scenes: tuple[PlannedScene, ...], model: str, data: bytes) -> dict[str, object]:
    """What the server counts for a job: the scenes it will voice, their characters, the model, the script revision.

    Characters are the sum of body lengths in code points (titles excluded, as `synth/check_body_chars.py`); the
    revision is the SHA-256 of the exact `script.md` bytes that were planned. The caller picks the scenes.
    """
    return {
        "scenes": len(scenes),
        "characters": sum(len(scene.body) for scene in scenes),
        "model": model,
        "revision": script_revision(data),
    }
