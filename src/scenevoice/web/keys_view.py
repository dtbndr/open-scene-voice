import json


def keys_view(stdout: str, region: str, ignored: list[str]) -> dict[str, object] | None:
    """The keys API shape from `keys status` stdout, or None when it is not the expected JSON."""
    try:
        status = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(status, dict) or not isinstance(status.get("path"), str) or not isinstance(status.get("keys"), dict):
        return None
    return {"path": status["path"], "keys": status["keys"], "suggested_region": region, "ignored_environment": ignored}
