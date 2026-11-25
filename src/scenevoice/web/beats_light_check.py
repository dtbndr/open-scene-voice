import re

_SHA256 = re.compile(r"[0-9a-f]{64}")


def beats_light_check(document: object) -> str | None:
    """The `script_sha256` of a sidecar that passes the light shape check, else None.

    Light means an object with exactly `version` 1, `script_sha256` (64 lowercase hex characters) and `scenes` (a
    list); the deeper checks are the CLI's (`web` cannot import `beats`).
    """
    if not isinstance(document, dict) or set(document) != {"version", "script_sha256", "scenes"}:
        return None
    version, sha256 = document["version"], document["script_sha256"]
    if type(version) is not int or version != 1 or not isinstance(document["scenes"], list):
        return None
    if not isinstance(sha256, str) or _SHA256.fullmatch(sha256) is None:
        return None
    return sha256
