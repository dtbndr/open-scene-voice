from dataclasses import dataclass


@dataclass(frozen=True)
class Scene:
    ordinal: int
    title: str
    body: str
    line: int
