from scenevoice.align.sentence_end import SENTENCE_END
from scenevoice.align.white_space import WHITE_SPACE_RUN


def sentence_offsets(body: str) -> list[int]:
    """Body offset of the first non-whitespace character of each sentence (see align contract)."""
    offsets: list[int] = []
    pending: int | None = None
    last_word = ""
    position = 0
    for run in WHITE_SPACE_RUN.finditer(body):
        if run.start() > position:
            if pending is None:
                pending = position
            last_word = body[position : run.start()]
        if pending is not None and (
            run.group().count("\n") >= 2 or SENTENCE_END.search(last_word)
        ):
            offsets.append(pending)
            pending = None
        position = run.end()
    if position < len(body) and pending is None:
        pending = position
    if pending is not None:
        offsets.append(pending)
    return offsets
