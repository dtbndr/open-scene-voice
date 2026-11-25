import io

import pytest

from scenevoice.progress import KINDS, Failure, event_line, split_line, write_event
from scenevoice.progress.failure_kind import failure_kind


def test_failure_equals_plain_string_and_is_str():
    f = Failure("boom", "other")
    assert f == "boom"
    assert isinstance(f, str)


def test_failure_carries_scene_line_status():
    f = Failure("boom", "bad_key", scene=2, line=7, status=401)
    assert (f.kind, f.scene, f.line, f.status) == ("bad_key", 2, 7, 401)


def test_failure_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Failure("boom", "nope")


PROVIDERS = ("tts", "openrouter")


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (400, "other"),
        (401, "bad_key"),
        (429, "quota"),
        (503, "provider_down"),
    ],
)
def test_status_maps_to_kind_for_every_provider(provider, status, kind):
    assert failure_kind(provider, status) == kind


@pytest.mark.parametrize(
    ("provider", "kind"), [("openrouter", "quota"), ("tts", "other")]
)
def test_402_differs_by_provider(provider, kind):
    assert failure_kind(provider, 402) == kind


@pytest.mark.parametrize("provider", PROVIDERS)
def test_no_status_with_transport_error_is_provider_down(provider):
    assert failure_kind(provider, None, transport=True) == "provider_down"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_no_status_without_transport_error_is_other(provider):
    assert failure_kind(provider, None) == "other"
    assert failure_kind(provider, None, transport=False) == "other"


def test_every_result_is_a_known_kind():
    for status in (None, 200, 401, 402, 429, 500):
        assert failure_kind("tts", status, transport=True) in KINDS


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("FAIL no key", ("fail", "no key")),
        ("NOTE careful", ("note", "careful")),
        ("OK done", ("ok", "done")),
    ],
)
def test_maps_leading_word_to_event(text: str, expected: tuple[str, str]) -> None:
    assert split_line("plan", text) == expected


def test_strips_own_command_prefix() -> None:
    assert split_line("pack", "scenevoice pack: FAIL bad") == ("fail", "bad")


def test_does_not_strip_another_commands_prefix() -> None:
    with pytest.raises(ValueError):
        split_line("pack", "scenevoice synth: FAIL bad")


@pytest.mark.parametrize("text", ["hello", "FAILED x"])
def test_unrecognised_text_raises(text: str) -> None:
    with pytest.raises(ValueError):
        split_line("plan", text)


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def write(self, text: str) -> int:
        self.calls.append(("write", text))
        return len(text)

    def flush(self) -> None:
        self.calls.append(("flush", ""))


class _NoFlush:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, text: str) -> int:
        self.writes.append(text)
        return len(text)


def test_one_write_equal_to_event_line_then_flush() -> None:
    rec = _Recorder()
    write_event(rec, "synth", "scene", "go", state="started", scene=1, total=2)
    expected = event_line("synth", "scene", "go", state="started", scene=1, total=2)
    assert rec.calls == [("write", expected), ("flush", "")]


def test_stream_without_flush_is_fine() -> None:
    stream = _NoFlush()
    write_event(stream, "plan", "ok", "done")
    assert stream.writes == [event_line("plan", "ok", "done")]


def test_message_is_not_altered() -> None:
    buf = io.StringIO()
    write_event(buf, "plan", "note", "a  b\nc")
    assert buf.getvalue() == event_line("plan", "note", "a  b\nc")
