from dataclasses import dataclass


@dataclass(frozen=True)
class JsonBody:
    """A parsed request body; `value` is None when the request carries no body."""

    value: object
