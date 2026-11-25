import threading

from .cli_runner import CliRunner
from .error_envelope import error_envelope
from .key_name_of import key_name_of
from .keys_failure import keys_failure
from .read_keys import read_keys
from .request import Request
from .response import Response
from .route_table import Handler


def put_key(run: CliRunner, lock: threading.Lock, region: str, ignored: list[str]) -> Handler:
    """PUT /api/keys/NAME with {"value": str}: the value goes to `keys set NAME` on stdin only, under the lock."""

    def handle(request: Request) -> Response:
        name = key_name_of(request.path)
        if name is None:
            return error_envelope("not_found", "Nothing is here.")
        body = request.json_body
        value = body.get("value") if isinstance(body, dict) else None
        if not isinstance(value, str) or value == "":
            return error_envelope("bad_request", "Enter a value to save.")
        with lock:
            result = run(["keys", "set", name], value.encode("utf-8"))
        if result.timed_out or result.returncode != 0:
            return keys_failure(result, value)
        return read_keys(run, region, ignored, after_write=True)

    return handle
