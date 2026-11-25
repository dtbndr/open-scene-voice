from urllib.parse import urlsplit


def normalise_path(path: str) -> str:
    """A request path as a single-slash, same-origin path: backslashes read as slashes, a scheme and host dropped."""
    path = path.replace("\\", "/")
    if not path.startswith("/"):
        path = urlsplit(path).path
    return "/" + path.lstrip("/")
