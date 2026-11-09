from scenevoice.align.match_constants import MATCH_THRESHOLD
from scenevoice.align.matched_indexes import matched_indexes
from scenevoice.align.seconds_to_ms import seconds_to_ms
from scenevoice.align.word_tokens import word_tokens


def match_scene(
    sentences: list[str], heard: list[tuple[str, float]]
) -> list[int | None]:
    """Return one start_ms (or None) per sentence, matching the whole scene at once."""
    script: list[str] = []
    owners: list[int] = []
    for index, sentence in enumerate(sentences):
        tokens = word_tokens(sentence)
        script.extend(tokens)
        owners.extend([index] * len(tokens))
    matched = matched_indexes(script, [token for token, _ in heard])
    totals = [0] * len(sentences)
    hits = [0] * len(sentences)
    first: dict[int, int] = {}
    for position, owner in enumerate(owners):
        totals[owner] += 1
        if position in matched:
            hits[owner] += 1
            first.setdefault(owner, position)
    result: list[int | None] = []
    for index in range(len(sentences)):
        if totals[index] == 0:
            result.append(None)
        elif hits[index] * 100 >= totals[index] * MATCH_THRESHOLD:
            result.append(seconds_to_ms(heard[matched[first[index]]][1]))
        else:
            result.append(None)
    return result
