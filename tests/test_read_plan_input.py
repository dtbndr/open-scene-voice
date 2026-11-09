import io

from scenevoice.synth.read_plan_input import read_plan_input
from scenevoice.validation import Violation


class FakeStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


class BrokenBuffer:
    def read(self):
        raise OSError(5, "Input/output error")


class BrokenStdin:
    buffer = BrokenBuffer()


class NoBufferStdin:
    pass


def _is_read_failure(result):
    return isinstance(result, Violation) and "cannot read file (" in result.message


def test_readable_file_returns_bytes(tmp_path):
    path = tmp_path / "plan.json"
    path.write_bytes(b"[1]")
    assert read_plan_input(str(path), None) == b"[1]"


def test_path_wins_over_stdin_which_is_not_touched(tmp_path):
    path = tmp_path / "plan.json"
    path.write_bytes(b"from file")
    assert read_plan_input(path, NoBufferStdin()) == b"from file"


def test_missing_path_is_a_read_failure(tmp_path):
    assert _is_read_failure(read_plan_input(str(tmp_path / "nope.json"), None))


def test_directory_as_plan_is_a_read_failure(tmp_path):
    assert _is_read_failure(read_plan_input(str(tmp_path), None))


def test_empty_stdin_is_a_read_failure():
    assert _is_read_failure(read_plan_input(None, FakeStdin(b"")))


def test_non_empty_stdin_returns_bytes():
    assert read_plan_input(None, FakeStdin(b"{}")) == b"{}"


def test_oserror_on_stdin_read_is_a_read_failure():
    assert _is_read_failure(read_plan_input(None, BrokenStdin()))


def test_stdin_without_buffer_is_a_read_failure():
    assert _is_read_failure(read_plan_input(None, NoBufferStdin()))
