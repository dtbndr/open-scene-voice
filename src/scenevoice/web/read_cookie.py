from .request import Request


def read_cookie(request: Request, name: str) -> str | None:
    """The first cookie called `name`; malformed pairs are skipped, nothing raises."""
    for header in request.header_values("cookie"):
        for pair in header.split(";"):
            key, separator, value = pair.partition("=")
            if separator and key.strip() == name:
                return value.strip()
    return None
