from .progress_vocabulary import FAILURE_KINDS


def known_kind(value: object) -> str:
    """The value if it is one of the six failure kinds, else `other`."""
    if isinstance(value, str) and value in FAILURE_KINDS:
        return value
    return "other"
