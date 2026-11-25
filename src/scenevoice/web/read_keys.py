import json

from .cli_runner import CliRunner
from .error_envelope import error_envelope
from .keys_failure import keys_failure
from .keys_view import keys_view
from .response import Response

AFTER_WRITE = "Your change may have been saved, but the key list could not be read afterwards. Reload to check."
UNREADABLE = "SceneVoice could not read the key list."


def read_keys(run: CliRunner, region: str, ignored: list[str], *, after_write: bool = False) -> Response:
    """Run `keys status` and answer with the keys view; after a write a failure says the result could not be read."""
    result = run(["keys", "status"], None)
    failed = result.timed_out or result.returncode != 0
    if failed and not after_write:
        return keys_failure(result)
    view = None if failed else keys_view(result.stdout, region, ignored)
    if view is None:
        return error_envelope("cli_failed", AFTER_WRITE if after_write else UNREADABLE)
    body = json.dumps(view, ensure_ascii=False).encode("utf-8")
    return Response(200, body, (("Content-Type", "application/json; charset=utf-8"),), no_store=True)
