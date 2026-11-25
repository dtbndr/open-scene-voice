import uuid


class SlotHandle:
    """A reserved place in the single job slot; the runner owns every field and changes them under its lock."""

    def __init__(self, kind: str, project: str) -> None:
        self.run = uuid.uuid4().hex
        self.kind = kind
        self.project = project
        self.started = False
        self.released = False
        self.refused = False
