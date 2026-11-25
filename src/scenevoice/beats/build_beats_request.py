import json

from scenevoice.beats.beats_constants import BEATS_MAX_TOKENS


def build_beats_request(model: str, messages: list[dict[str, str]]) -> bytes:
    """Return the JSON request body bytes with a fixed key order.

    The request shape is unobserved until live acceptance. The default ASCII
    escaping keeps UTF-8 encoding total, even for a lone surrogate.
    """
    body = {"model": model, "messages": messages, "max_tokens": BEATS_MAX_TOKENS}
    return json.dumps(body).encode("utf-8")
