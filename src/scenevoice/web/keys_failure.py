from .cli_result import CliResult
from .error_envelope import error_envelope
from .response import Response

FAIL_PREFIX = "scenevoice keys: FAIL "
GENERIC = "The key could not be saved."


def keys_failure(result: CliResult, secret: str | None = None) -> Response:
    """Map a failed child run to the envelope: its one FAIL line is 400, anything else is 502.

    A message that contains `secret` is replaced by a fixed one. NOTE lines and other stderr are never passed on.
    """
    if not result.timed_out and result.returncode != -1:
        for line in result.stderr.split("\n"):
            message = line[len(FAIL_PREFIX) :].strip() if line.startswith(FAIL_PREFIX) else ""
            if message:
                needle = secret.strip() if secret else ""
                leaked = needle != "" and needle in message
                return error_envelope("bad_request", GENERIC if leaked else message)
    return error_envelope("cli_failed", "SceneVoice could not run the key command.")
