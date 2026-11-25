from typing import Literal

from .cookie_name import cookie_name
from .read_cookie import read_cookie
from .redeem_location import redeem_location
from .request import Request
from .token_matches import token_matches

Decision = Literal["allowed", "redeem", "stale"]


def authenticate(request: Request, token: str, port: int) -> Decision:
    """A redeemable link wins (it refreshes the cookie), then a valid cookie, else stale."""
    if redeem_location(request, token) is not None:
        return "redeem"
    cookie = read_cookie(request, cookie_name(port))
    if cookie is not None and token_matches(cookie, token):
        return "allowed"
    return "stale"
