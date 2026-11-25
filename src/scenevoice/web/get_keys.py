from .cli_runner import CliRunner
from .read_keys import read_keys
from .request import Request
from .response import Response
from .route_table import Handler


def get_keys(run: CliRunner, region: str, ignored: list[str]) -> Handler:
    """GET /api/keys: run `keys status`; takes no lock because the CLI writes the key file atomically."""

    def handle(request: Request) -> Response:
        return read_keys(run, region, ignored)

    return handle
