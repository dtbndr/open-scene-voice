import io
import json

import pytest

from scenevoice.cli.main import main

BASE = ["--voice", "Charon", "--model", "gemini-3.8-flash-tts"]


class FailingStdin:
    def __init__(self):
        self.touched = []

    @property
    def buffer(self):
        self.touched.append("buffer")
        raise AssertionError("stdin was read")

    def isatty(self):
        self.touched.append("isatty")
        raise AssertionError("stdin was probed")


@pytest.fixture
def probes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "plan.json").write_text(json.dumps({"scenes": [{"ordinal": 1, "title": "t", "body": "b"}]}))
    (tmp_path / "out").mkdir()
    stdin = FailingStdin()
    monkeypatch.setattr("sys.stdin", stdin)
    opened = []
    real_open = io.open

    def spy_open(file, *args, **kwargs):
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(io, "open", spy_open)
    calls = []

    def factory(env, model):
        calls.append(env)
        raise AssertionError("factory called")

    class P:
        pass

    p = P()
    p.stdin, p.opened, p.factory, p.factory_calls = stdin, opened, factory, calls
    return p


def argv(*extra):
    return ["synth", "plan.json", "--out", "out", *BASE, *extra]


@pytest.fixture
def captured_scene(monkeypatch):
    seen = []

    def fake_run_synth(**kwargs):
        seen.append(kwargs["scene"])
        return 0

    monkeypatch.setattr("scenevoice.cli.synth.run_synth", fake_run_synth)
    return seen


def test_scene_parses_to_int_and_reaches_core(captured_scene):
    assert main(argv("--scene", "2"), provider_factory=lambda e, m: None) == 0
    assert captured_scene == [2]


def test_omitted_scene_passes_none(captured_scene):
    assert main(argv(), provider_factory=lambda e, m: None) == 0
    assert captured_scene == [None]


def test_repeated_scene_keeps_last(captured_scene):
    main(argv("--scene", "1", "--scene", "3"), provider_factory=lambda e, m: None)
    assert captured_scene == [3]


@pytest.mark.parametrize("token", ["abc", "1.5", ""])
def test_non_integer_scene_is_usage_error_before_io(probes, capsys, token):
    with pytest.raises(SystemExit) as exc:
        main(argv("--scene", token), provider_factory=probes.factory)
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "argument --scene: invalid int value" in captured.err.split("error:", 1)[1]
    assert probes.stdin.touched == []
    assert probes.factory_calls == []
    assert not [f for f in probes.opened if f.endswith((".env", "plan.json"))]


@pytest.mark.parametrize("value", ["0", "-1", "99", "99999999999999999999"])
def test_out_of_range_integer_reaches_core(probes, capsys, value):
    code = main(argv("--scene", value), provider_factory=probes.factory)
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    last = captured.err.splitlines()[-1]
    assert last == f"scenevoice synth: FAIL --scene {int(value)} is out of range (the plan has 1 scenes)"
    assert probes.factory_calls == []


def test_help_describes_scene(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["synth", "--help"])
    assert exc.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "--scene" in text
    assert "one provider call" in text
    assert "replaces DIR/audio/NNN.wav" in text
    assert "must already exist" in text
    assert "pass the original --voice" in text and "again" in text and "--instruction" in text
