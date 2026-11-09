import re

from scenevoice.align.sentence_end import SENTENCE_END
from scenevoice.align.white_space import WHITE_SPACE_RUN


def split_sentences(body: str) -> list[str]:
    """Split a plan body into collapsed sentence texts (see align contract)."""
    text = body.replace("\r\n", "\n")
    sentences: list[str] = []
    words: list[str] = []
    for part in re.split(f"({WHITE_SPACE_RUN.pattern})", text):
        if not part:
            continue
        if WHITE_SPACE_RUN.fullmatch(part):
            if part.count("\n") >= 2 and words:
                sentences.append(" ".join(words))
                words = []
            elif words and SENTENCE_END.search(words[-1]):
                sentences.append(" ".join(words))
                words = []
        else:
            words.append(part)
    if words:
        sentences.append(" ".join(words))
    return sentences
