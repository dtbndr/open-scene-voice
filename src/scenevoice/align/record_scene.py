from scenevoice.align.scene_timings import SceneTimings
from scenevoice.align.seconds_to_ms import seconds_to_ms
from scenevoice.align.sentence_offsets import sentence_offsets
from scenevoice.align.split_sentences import split_sentences
from scenevoice.align.word_tokens import word_tokens
from scenevoice.pack import LineTiming
from scenevoice.synth import Alignment, PlanScene


def _element_index(lengths: list[int], offset: int) -> int:
    """Index of the first element whose cumulative length exceeds the offset."""
    total = 0
    for index, length in enumerate(lengths):
        total += length
        if total > offset:
            return index
    raise IndexError(offset)


def record_scene(scene: PlanScene, sha256: str, alignment: Alignment) -> SceneTimings | str:
    """Line starts from a record alignment; a one-line reason (no scene prefix) on overflow.

    Precondition: the joined characters equal scene.body (checked by the caller).
    """
    lengths = [len(element) for element in alignment.characters]
    sentences = split_sentences(scene.body)
    offsets = sentence_offsets(scene.body)
    lines: list[LineTiming] = []
    for text, offset in zip(sentences, offsets, strict=True):
        if not word_tokens(text):
            lines.append(LineTiming(text, None))
            continue
        index = _element_index(lengths, offset)
        start_ms = seconds_to_ms(alignment.character_start_times_seconds[index])
        if start_ms is None:
            return "alignment start time is not representable in milliseconds"
        lines.append(LineTiming(text, start_ms))
    return SceneTimings(scene.ordinal, sha256, lines)
