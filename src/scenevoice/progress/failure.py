"""A str that also carries a progress kind and optional location."""

from scenevoice.progress.kinds import KINDS


class Failure(str):
    """The failure message, equal to the plain string, plus its classification."""

    kind: str
    scene: int | None
    line: int | None
    status: int | None

    def __new__(
        cls,
        message: str,
        kind: str,
        *,
        scene: int | None = None,
        line: int | None = None,
        status: int | None = None,
    ) -> "Failure":
        if kind not in KINDS:
            raise ValueError(f"unknown failure kind: {kind!r}")
        self = super().__new__(cls, message)
        self.kind = kind
        self.scene = scene
        self.line = line
        self.status = status
        return self
