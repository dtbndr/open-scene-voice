import io
import json

from wav_helper import make_wav


def plan_bytes(scenes: list[dict]) -> bytes:
    return json.dumps({"scenes": scenes}).encode("utf-8")


def scene(i: int, title: str = "T", body: str = "Hello.") -> dict:
    return {"ordinal": i, "title": title, "body": body}


def write_plan(tmp_path, scenes: list[dict]):
    path = tmp_path / "plan.json"
    path.write_bytes(plan_bytes(scenes))
    return path


def put_wav(directory, ordinal: int, frames: int = 24000) -> None:
    (directory / "audio").mkdir(exist_ok=True)
    (directory / "audio" / f"{ordinal:03d}.wav").write_bytes(make_wav(frames))


class FakeStdin:
    def __init__(self, data: bytes, tty: bool = False):
        self.buffer = io.BytesIO(data)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty
