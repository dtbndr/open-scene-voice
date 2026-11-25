import re

from .valid_text import valid_text

_REVISION = re.compile(r"[0-9a-f]{64}")


def _count(value: object) -> bool:
    return type(value) is int and value >= 0


def parse_confirm(value: object, *, with_model: bool, with_characters: bool) -> dict[str, object] | None:
    """The numbers the creator confirmed, with exactly the keys the kind needs; None when anything is off."""
    keys = {"scenes", "revision"} | ({"characters"} if with_characters else set()) | ({"model"} if with_model else set())
    if not isinstance(value, dict) or set(value) != keys:
        return None
    revision = value["revision"]
    if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
        return None
    if not _count(value["scenes"]) or (with_characters and not _count(value["characters"])):
        return None
    if with_model and not valid_text(value["model"]):
        return None
    return dict(value)
