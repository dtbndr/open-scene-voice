from urllib.parse import parse_qsl, quote, urlencode

from .normalise_path import normalise_path
from .request import Request
from .token_matches import token_matches


def redeem_location(request: Request, token: str) -> str | None:
    """Where to send a redeemable navigation, or None. Never redeems HEAD, non-GET, /api/ or odd paths."""
    if request.method != "GET":
        return None
    if not all(0x21 <= ord(ch) <= 0x7E for ch in request.path):
        return None
    try:
        path = normalise_path(request.path)
    except ValueError:
        return None
    if request.path.startswith("/api/") or path.startswith("/api/"):
        return None
    pairs = parse_qsl(request.query, keep_blank_values=True)
    tokens = [value for key, value in pairs if key == "token"]
    if len(tokens) != 1 or not token_matches(tokens[0], token):
        return None
    rest = urlencode([(key, value) for key, value in pairs if key != "token"])
    location = quote(path, safe="/%:@!$&'()*+,;=-._~")
    return f"{location}?{rest}" if rest else location
