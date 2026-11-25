def path_exists_message(path: object, *, command: str) -> str:
    """The one-line refusal shared by the pre-check and the exclusive create."""
    return f"{path} already exists; choose a new --out path ({command} never overwrites)"
