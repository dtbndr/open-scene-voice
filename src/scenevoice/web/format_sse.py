import json
from collections.abc import Mapping


def format_sse(job: int, event: Mapping[str, object]) -> bytes:
    """One server-sent event: `id: <job>-<seq>` and one `data:` line of ASCII JSON (so no raw separator can split it)."""
    data = json.dumps(event, ensure_ascii=True)
    return f"id: {job}-{event['seq']}\ndata: {data}\n\n".encode("ascii")
