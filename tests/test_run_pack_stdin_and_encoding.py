import io
import os

import pytest
from pack_run_helper import FakeStdin, put_wav, scene, write_plan

from scenevoice.pack import run_pack

_SCENES = [scene(1, "One"), scene(2, "Two")]
_MARKER = "ZXQMARKERZXQ"


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


def _out(tmp_path, name="out"):
    out = tmp_path / name
    out.mkdir()
    put_wav(out, 1)
    put_wav(out, 2)
    return out


def test_terminal_stdin_without_plan_fails_before_any_io(tmp_path):
    stdin = _TtyStdin()
    err = io.StringIO()
    code = run_pack(None, stdin, tmp_path / "no-such-dir", err)
    assert code == 1
    assert stdin.reads == 0
    text = err.getvalue()
    assert text.startswith("scenevoice pack: FAIL ") and "stdin" in text
    assert "directory" not in text


def test_unusable_stdin_without_plan_fails(tmp_path):
    out = _out(tmp_path)
    data = write_plan(tmp_path, _SCENES).read_bytes()
    for error in (AttributeError("x"), ValueError("closed")):
        err = io.StringIO()
        code = run_pack(None, _BrokenStdin(error, data), out, err)
        assert code == 1
        assert err.getvalue().startswith("scenevoice pack: FAIL ")
        assert "stdin" in err.getvalue()
        assert not (out / "scene_manifest.csv").exists()


def test_terminal_stdin_is_ignored_when_plan_given(tmp_path):
    out = _out(tmp_path)
    err = io.StringIO()
    code = run_pack(write_plan(tmp_path, _SCENES), FakeStdin(b"", tty=True), out, err)
    assert code == 0


def test_message_never_echoes_title_text(tmp_path):
    out = _out(tmp_path)
    plan = write_plan(tmp_path, [scene(1, _MARKER + "\ud800"), scene(2)])
    err = io.StringIO()
    assert run_pack(plan, FakeStdin(b""), out, err) == 1
    assert err.getvalue().startswith("scenevoice pack: FAIL ")
    assert _MARKER not in err.getvalue()


def _assert_ascii_fail(code, raw, stream):
    stream.flush()
    assert code == 1
    assert raw.getvalue().decode("ascii").startswith("scenevoice pack: FAIL ")


def test_stderr_safe_with_surrogate_title(tmp_path):
    out = _out(tmp_path)
    raw, stream = _ascii_stderr()
    plan = write_plan(tmp_path, [scene(1, "a\ud800b"), scene(2)])
    _assert_ascii_fail(run_pack(plan, FakeStdin(b""), out, stream), raw, stream)


def test_stderr_safe_with_surrogate_escaped_plan_path(tmp_path):
    out = _out(tmp_path)
    raw, stream = _ascii_stderr()
    plan = tmp_path / os.fsdecode(b"plan-\xff.json")
    _assert_ascii_fail(run_pack(plan, FakeStdin(b""), out, stream), raw, stream)


def test_stderr_safe_with_non_ascii_dir(tmp_path):
    raw, stream = _ascii_stderr()
    plan = write_plan(tmp_path, _SCENES)
    missing = tmp_path / "déjà-日本"
    _assert_ascii_fail(run_pack(plan, FakeStdin(b""), missing, stream), raw, stream)


def test_ok_line_safe_with_non_ascii_dir(tmp_path):
    out = _out(tmp_path, "déjà-日本")
    raw, stream = _ascii_stderr()
    code = run_pack(write_plan(tmp_path, _SCENES), FakeStdin(b""), out, stream)
    stream.flush()
    assert code == 0
    assert raw.getvalue().decode("ascii").startswith("scenevoice pack: OK 2 scenes")
    assert (out / "scene_manifest.csv").exists()


def test_ok_line_safe_with_surrogate_escaped_dir(tmp_path):
    try:
        out = _out(tmp_path, os.fsdecode(b"out-\xff"))
    except OSError:
        pytest.skip("filesystem rejects non-UTF-8 names")
    raw, stream = _ascii_stderr()
    code = run_pack(write_plan(tmp_path, _SCENES), FakeStdin(b""), out, stream)
    stream.flush()
    assert code == 0
    assert raw.getvalue().decode("ascii").startswith("scenevoice pack: OK 2 scenes")


def test_stderr_safe_with_surrogate_escaped_missing_dir(tmp_path):
    raw, stream = _ascii_stderr()
    plan = write_plan(tmp_path, _SCENES)
    missing = tmp_path / os.fsdecode(b"gone-\xff")
    _assert_ascii_fail(run_pack(plan, FakeStdin(b""), missing, stream), raw, stream)
