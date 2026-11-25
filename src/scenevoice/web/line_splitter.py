class LineSplitter:
    """Split a byte stream into text lines on `\\n` only, dropping any line longer than `limit` bytes.

    Never `str.splitlines`: U+2028 and U+0085 stay inside their line. Invalid UTF-8 is replaced. A dropped line is
    skipped to its newline and the lines after it still arrive, whatever the chunking.
    """

    def __init__(self, limit: int = 65536) -> None:
        self.limit = limit
        self._pending = b""
        self._dropping = False

    def feed(self, chunk: bytes) -> list[str]:
        """Complete lines found after adding `chunk`."""
        lines: list[str] = []
        parts = (self._pending + chunk).split(b"\n")
        self._pending = parts.pop()
        for raw in parts:
            if self._dropping:
                self._dropping = False
            elif len(raw) <= self.limit:
                lines.append(raw.decode("utf-8", errors="replace"))
        if len(self._pending) > self.limit:
            self._pending = b""
            self._dropping = True
        return lines

    def finish(self) -> list[str]:
        """The unterminated final line, if there is one and it was not dropped."""
        tail, dropping = self._pending, self._dropping
        self._pending, self._dropping = b"", False
        if dropping or not tail:
            return []
        return [tail.decode("utf-8", errors="replace")]
