from .white_space import WHITE_SPACE_RUN


def collapse_text(text: str) -> str:
    """The text with every run of Unicode White_Space dropped to one space and the ends trimmed.

    This is what the align sentence texts join to (`" ".join(split_sentences(body))`); a drift test pins it.
    """
    return " ".join(part for part in WHITE_SPACE_RUN.split(text) if part)
