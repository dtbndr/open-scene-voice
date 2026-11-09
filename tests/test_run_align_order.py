"""Each check is proved by a setup in which a wrong order would give a different message."""

import io
import json

from align_run_helper import ENV, HELLO, PREFIX, Fake, NoTerminal, body, go, pack_dir
from record_helper import RECORD_FILE
from wav_helper import make_wav

from scenevoice.align.run_align import run_align
from scenevoice.pack import check_pack_audio_dir, check_pack_dir, check_pack_plan


class _Buffer:
    def __init__(self, owner):
        self.owner = owner

    def read(self):
        self.owner.reads += 1
        return b"{}"


class Terminal:
    def __init__(self):
        self.reads = 0
        self.buffer = _Buffer(self)

    def isatty(self):
        return True


def _fail_line(message):
    return f"{PREFIX}FAIL {message}\n"


def test_terminal_stdin_is_checked_before_the_plan_is_read(tmp_path):
    _, out, _ = pack_dir(tmp_path, ["Hi."])
    stdin = Terminal()
    code, err, _ = go(None, out, Fake([]), tmp_path, stdin=stdin)
    assert code == 1
    assert stdin.reads == 0
    assert "terminal" in err and err.startswith(PREFIX + "FAIL ")


def test_plan_is_checked_before_dir(tmp_path):
    plan_path, _, _ = pack_dir(tmp_path, ["Hi."])
    scenes = [{"ordinal": i, "title": "T", "body": "Hi."} for i in range(1, 1001)]
    plan_path.write_text(json.dumps({"scenes": scenes}))
    missing = tmp_path / "nodir"
    plan_problem = check_pack_plan(plan_path, None)
    assert isinstance(plan_problem, str) and "exceeds the maximum" in plan_problem
    assert check_pack_dir(missing) is not None
    code, err, _ = go(plan_path, missing, Fake([]), tmp_path)
    assert (code, err) == (1, _fail_line(plan_problem))


def test_dir_is_checked_before_audio(tmp_path):
    plan_path, _, _ = pack_dir(tmp_path, ["Hi."])
    missing = tmp_path / "nodir"
    code, err, _ = go(plan_path, missing, Fake([]), tmp_path)
    assert (code, err) == (1, _fail_line(check_pack_dir(missing)))
    assert check_pack_audio_dir(missing) != check_pack_dir(missing)


def test_audio_is_checked_before_the_timings_path(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."], make_wavs=False)
    (out / "audio").rmdir()
    (out / "line_timings.json").mkdir()
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert (code, err) == (1, _fail_line(check_pack_audio_dir(out)))
    assert "line_timings.json" not in err


def test_timings_path_is_checked_before_any_wav(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi.", "Hi."])
    (out / "line_timings.json").mkdir()
    (out / "audio" / "001.wav").write_bytes(b"not a wav")
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert code == 1
    assert "line_timings.json" in err
    assert "audio/001.wav" not in err


def test_first_failing_wav_scene_is_reported(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi.", "Hi.", "Hi."])
    (out / "audio" / "002.wav").write_bytes(make_wav(999))
    (out / "audio" / "003.wav").unlink()
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert code == 1
    assert err.startswith(PREFIX + "FAIL scene 2: audio/002.wav")
    assert "003" not in err


def test_wavs_are_checked_before_the_key(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi.", "Hi."])
    (out / "audio" / "002.wav").unlink()
    code, err, _ = go(plan_path, out, Fake([]), tmp_path, env={})
    assert code == 1
    assert err.startswith(PREFIX + "FAIL scene 2: audio/002.wav")
    assert "OPENROUTER_API_KEY" not in err


def test_key_is_checked_before_the_factory_and_any_call(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there.", "Hello there."])
    fake = Fake([body(HELLO)] * 2)
    code, err, keys = go(plan_path, out, fake, tmp_path, env={"OPENROUTER_API_KEY": "  "})
    assert code == 1
    assert err == _fail_line("OPENROUTER_API_KEY is not set")
    assert keys == [] and fake.received == []


def test_factory_is_called_once_after_the_checks_and_before_the_first_call(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there.", "Hello there."])
    events = []
    fake = Fake([body(HELLO)] * 2)

    def transcriber(wav):
        events.append("call")
        return fake(wav)

    def factory(key):
        events.append("factory")
        return transcriber

    code = run_align(
        plan_path, NoTerminal(), ENV, tmp_path / "no.env", out, factory, io.StringIO()
    )
    assert code == 0
    assert events == ["factory", "call", "call"]


def _malformed_record(out):
    (out / RECORD_FILE).write_text("{not json", encoding="utf-8")


def test_wavs_are_checked_before_the_record(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi.", "Hi."])
    (out / "audio" / "002.wav").unlink()
    _malformed_record(out)
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert code == 1
    assert err.startswith(PREFIX + "FAIL scene 2: audio/002.wav")
    assert RECORD_FILE not in err


def test_timings_path_is_checked_before_the_record(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    (out / "line_timings.json").mkdir()
    _malformed_record(out)
    code, err, _ = go(plan_path, out, Fake([]), tmp_path)
    assert code == 1
    assert "line_timings.json" in err
    assert RECORD_FILE not in err


def test_record_is_checked_before_the_key(tmp_path):
    """Mutation: moving check 5a after check 6 reports the key instead of the record."""
    plan_path, out, _ = pack_dir(tmp_path, ["Hi."])
    _malformed_record(out)
    code, err, _ = go(plan_path, out, Fake([]), tmp_path, env={})
    assert code == 1
    assert RECORD_FILE in err
    assert "OPENROUTER_API_KEY" not in err


def test_record_is_checked_before_the_factory_and_any_call(tmp_path):
    plan_path, out, _ = pack_dir(tmp_path, ["Hello there.", "Hello there."])
    _malformed_record(out)
    fake = Fake([body(HELLO)] * 2)
    code, err, keys = go(plan_path, out, fake, tmp_path)
    assert code == 1
    assert RECORD_FILE in err
    assert keys == [] and fake.received == []
