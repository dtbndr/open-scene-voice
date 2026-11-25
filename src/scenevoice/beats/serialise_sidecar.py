"""Canonical text of a beats sidecar."""

import json
from typing import Any


def serialise_sidecar(doc: dict[str, Any]) -> str:
    """Return the sidecar as text: dict key order kept, non-ASCII kept, two-space indent, one trailing newline."""
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
