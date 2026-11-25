from .authenticate import authenticate
from .redeem_token import redeem_token
from .request import Request
from .response import Response
from .route_table import Gate
from .stale_response import stale_response


def make_gate(token: str, port: int) -> Gate:
    """The real gate for make_server: nothing passes without the cookie except a redeemable link and the stale page."""

    def gate(request: Request) -> Response | None:
        decision = authenticate(request, token, port)
        if decision == "allowed":
            return None
        if decision == "redeem":
            return redeem_token(request, token, port)
        return stale_response(request)

    return gate
