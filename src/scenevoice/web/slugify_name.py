import re
import unicodedata

_MAX = 64


def slugify_name(name: str) -> str:
    """The project id for a creator's name: ASCII lowercase words joined by `-`, at most 64 characters."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    return slug[:_MAX].strip("-") or "untitled"
