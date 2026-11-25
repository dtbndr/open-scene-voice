from collections.abc import Callable, Mapping

from .request import Request
from .response import Response
from .stream_response import StreamResponse

Handler = Callable[[Request], Response | StreamResponse]
Gate = Callable[[Request], Response | None]
# raw path -> method -> handler; HEAD is looked up as GET. Build one per server, never share a module global.
RouteTable = Mapping[str, Mapping[str, Handler]]
