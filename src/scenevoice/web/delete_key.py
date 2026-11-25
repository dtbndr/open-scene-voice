import threading

from .cli_runner import CliRunner
from .error_envelope import error_envelope
from .key_name_of import key_name_of
from .keys_failure import keys_failure
from .read_keys import read_keys
from .request import Request
from .response import Response
from .route_table import Handler


def delete_key(run: CliRunner, lock: threading.Lock, region: str, ignored: list[str]) -> Handler:
    """DELETE /api/keys/NAME: `keys remove NAME` under the same lock as PUT, then a fresh status."""

    def handle(request: Request) -> Response:
        name = key_name_of(request.path)
        if name is None:
            return error_envelope("not_found", "Nothing is here.")
        with lock:
            result = run(["keys", "remove", name], None)
        if result.timed_out or result.returncode != 0:
            return keys_failure(result)
        return read_keys(run, region, ignored, after_write=True)

    return handle
