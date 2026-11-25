"""Run-only rules: the stdin guard when no PLAN is given, and ASCII-safe stderr lines."""

import io
import os

import pytest
from pack_run_helper import FakeStdin, make_out, scene, write_plan

from scenevoice.pack import run_pack


class _TtyStdin(FakeStdin):
    def __init__(self):
        super().__init__(b"", tty=True)
        self.reads = 0
        self.buffer = self

    def read(self, *a):
        self.reads += 1
        return b""


class _BrokenStdin:
    def __init__(self, error, data=b""):
        self._error = error
        self.buffer = io.BytesIO(data)

    def isatty(self):
        raise self._error


def _ascii_stderr():
    raw = io.BytesIO()
    return raw, io.TextIOWrapper(raw, encoding="ascii", errors="strict", write_through=True)


def test_terminal_stdin_without_plan_fails_before_any_io(tmp_path):
    stdin = _TtyStdin()
    err = io.StringIO()
    code = run_pack(None, stdin, tmp_path / "no-such-dir", err)
    assert code == 1
    assert stdin.reads == 0
    text = err.getvalue()
    assert text.startswith("scenevoice pack: FAIL ") and "stdin" in text
    assert "directory" not in text


@pytest.mark.parametrize("error", [AttributeError("x"), ValueError("closed")], ids=["attribute", "closed"])
def test_unusable_stdin_without_plan_fails(tmp_path, error):
    out = make_out(tmp_path)
    data = write_plan(tmp_path).read_bytes()
    err = io.StringIO()
    code = run_pack(None, _BrokenStdin(error, data), out, err)
    assert code == 1
    assert err.getvalue().startswith("scenevoice pack: FAIL ") and "stdin" in err.getvalue()
    assert not (out / "scene_manifest.csv").exists()


def test_terminal_stdin_is_ignored_when_plan_given(tmp_path):
    out = make_out(tmp_path)
    code = run_pack(write_plan(tmp_path), FakeStdin(b"", tty=True), out, io.StringIO())
    assert code == 0


def _surrogate_title(tmp_path):
    return write_plan(tmp_path, [scene(1, "a\ud800b"), scene(2)]), make_out(tmp_path)


def _surrogate_plan_path(tmp_path):
    return tmp_path / os.fsdecode(b"plan-\xff.json"), make_out(tmp_path)


def _non_ascii_missing_dir(tmp_path):
    return write_plan(tmp_path), tmp_path / "déjà-日本"


def _surrogate_missing_dir(tmp_path):
    return write_plan(tmp_path), tmp_path / os.fsdecode(b"gone-\xff")


@pytest.mark.parametrize(
    "case", [_surrogate_title, _surrogate_plan_path, _non_ascii_missing_dir, _surrogate_missing_dir]
)
def test_fail_line_is_ascii_for_non_ascii_input(tmp_path, case):
    plan, out = case(tmp_path)
    raw, stream = _ascii_stderr()
    code = run_pack(plan, FakeStdin(b""), out, stream)
    stream.flush()
    assert code == 1
    assert raw.getvalue().decode("ascii").startswith("scenevoice pack: FAIL ")


@pytest.mark.parametrize("name", ["déjà-日本", os.fsdecode(b"out-\xff")], ids=["non-ascii", "surrogate-escaped"])
def test_ok_line_is_ascii_for_non_ascii_dir(tmp_path, name):
    try:
        out = make_out(tmp_path, name)
    except OSError:
        if "\udcff" not in name:
            raise
        pytest.skip("filesystem rejects non-UTF-8 names")
    raw, stream = _ascii_stderr()
    code = run_pack(write_plan(tmp_path), FakeStdin(b""), out, stream)
    stream.flush()
    assert code == 0
    assert raw.getvalue().decode("ascii").startswith("scenevoice pack: OK 2 scenes")
    assert (out / "scene_manifest.csv").exists()
