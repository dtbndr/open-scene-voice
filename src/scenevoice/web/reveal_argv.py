def reveal_argv(platform: str, directory: str) -> list[str] | None:
    """The argument list that shows `directory` in the platform's file manager, or None where none is supported.

    `platform` is `sys.platform`, passed in by the caller. The directory must be absolute so it can never be read
    as an option; a relative one is a programming error.
    """
    if not directory.startswith("/"):
        raise ValueError("the directory to reveal must be absolute")
    if platform == "darwin":
        return ["open", directory]
    if platform.startswith("linux"):
        return ["xdg-open", directory]
    return None
