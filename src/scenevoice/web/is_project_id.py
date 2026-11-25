import re

# One source for the validator and the route shapes, so the two can never drift.
PROJECT_ID_PATTERN = r"[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?"
_PROJECT_ID = re.compile(PROJECT_ID_PATTERN)


def is_project_id(value: str) -> bool:
    """True for a valid project id (also the folder name); `fullmatch` so a trailing newline fails."""
    return _PROJECT_ID.fullmatch(value) is not None
