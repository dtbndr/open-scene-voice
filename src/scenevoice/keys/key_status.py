from scenevoice.keys.key_names import KEY_NAMES, NON_SECRET_NAMES


def key_status(raw: dict[str, str]) -> dict[str, dict[str, bool | str]]:
    """Per-name saved flag in KEY_NAMES order; a blank value is not saved.
    Only the non-secret names ever carry their value."""
    status: dict[str, dict[str, bool | str]] = {}
    for name in KEY_NAMES:
        value = raw.get(name, "")
        if value.strip() == "":
            status[name] = {"saved": False}
        elif name in NON_SECRET_NAMES:
            status[name] = {"saved": True, "value": value}
        else:
            status[name] = {"saved": True}
    return status
