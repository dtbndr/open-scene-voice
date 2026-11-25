import re

_RUN = re.compile(r"[0-9a-f]{32}")


def is_run_id(value: object) -> bool:
    """True for a run id as the runner makes it: 32 lowercase hex characters (uuid4 hex)."""
    return isinstance(value, str) and _RUN.fullmatch(value) is not None
