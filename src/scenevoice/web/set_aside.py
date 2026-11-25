from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SetAside:
    """The files one Start again attempt renamed away: (original path, backup path), in the order done. Nothing is globbed later."""

    moves: tuple[tuple[Path, Path], ...] = ()


class SetAsideFailed(Exception):
    """A rename failed part way; `done` holds the moves that did happen (to be put back)."""

    def __init__(self, done: SetAside) -> None:
        super().__init__("set-aside failed")
        self.done = done
