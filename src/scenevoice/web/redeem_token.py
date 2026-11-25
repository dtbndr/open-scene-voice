from .cookie_name import cookie_name
from .redeem_location import redeem_location
from .request import Request
from .response import Response
from .stale_response import stale_response


def redeem_token(request: Request, token: str, port: int) -> Response:
    """303 to the same path without the token, setting the session cookie; stale if the request is not redeemable."""
    location = redeem_location(request, token)
    if location is None:
        return stale_response(request)
    cookie = f"{cookie_name(port)}={token}; HttpOnly; SameSite=Lax; Path=/"
    return Response(303, b"", (("Location", location), ("Set-Cookie", cookie)), no_store=True)
