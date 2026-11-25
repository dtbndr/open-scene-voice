from scenevoice.align.split_sentences import split_sentences
from scenevoice.validation.scene import Scene


def segment_scenes(scenes: list[Scene]) -> list[list[str]]:
    """Return, per scene, the sentence segments of its body (see align contract)."""
    return [split_sentences(scene.body) for scene in scenes]
