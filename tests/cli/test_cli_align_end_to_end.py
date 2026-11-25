import json
import sys

import pytest
from align_run_helper import HELLO, KEY, Fake, NoTerminal, body, pack_dir
from pack_run_helper import FakeStdin

from scenevoice.cli.main import main

TEXTS = ["Hello there.", "Hello there."]


def bodies():
    return [body(HELLO), body(HELLO)]


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(sys, "stdin", NoTerminal())


def factory_for(fake, keys):
    def factory(key):
        keys.append(key)
        return fake

    return factory


def test_two_scene_run_with_process_key(tmp_path, monkeypatch, capsys):
    plan, out, wavs = pack_dir(tmp_path, TEXTS)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    fake, keys = Fake(bodies()), []
    code = main(["align", str(plan), str(out)], transcriber_factory=factory_for(fake, keys))
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert lines[0] == "scenevoice align: NOTE no synth_record.json, all scenes transcribed"
    assert lines[-1].startswith("scenevoice align: OK 2 scenes")
    assert fake.received == wavs
    assert keys == [KEY]
    data = json.loads((out / "line_timings.json").read_text())
    assert data


def test_one_positional_reads_plan_from_stdin(tmp_path, monkeypatch, capsys):
    plan, out, _ = pack_dir(tmp_path, TEXTS)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    monkeypatch.setattr(sys, "stdin", FakeStdin(plan.read_bytes()))
    fake = Fake(bodies())
    code = main(["align", str(out)], transcriber_factory=factory_for(fake, []))
    assert code == 0
    assert len(fake.received) == 2
    assert capsys.readouterr().out == ""


def test_key_from_dotenv_in_cwd(tmp_path, capsys):
    plan, out, _ = pack_dir(tmp_path, TEXTS)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=from-dotenv\n")
    fake, keys = Fake(bodies()), []
    code = main(["align", str(plan), str(out)], transcriber_factory=factory_for(fake, keys))
    assert code == 0
    assert keys == ["from-dotenv"]
    assert "from-dotenv" not in capsys.readouterr().err


def test_process_key_wins_over_dotenv(tmp_path, monkeypatch):
    plan, out, _ = pack_dir(tmp_path, TEXTS)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=from-dotenv\n")
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    fake, keys = Fake(bodies()), []
    assert main(["align", str(plan), str(out)], transcriber_factory=factory_for(fake, keys)) == 0
    assert keys == [KEY]


def test_missing_key_exits_1_naming_it_with_zero_calls(tmp_path, capsys):
    plan, out, _ = pack_dir(tmp_path, TEXTS)
    fake, keys = Fake(bodies()), []
    code = main(["align", str(plan), str(out)], transcriber_factory=factory_for(fake, keys))
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "OPENROUTER_API_KEY" in captured.err
    assert fake.received == [] and keys == []
    assert not (out / "line_timings.json").exists()


def test_malformed_dotenv_line_logs_nothing_extra(tmp_path, monkeypatch, capsys):
    plan, out, _ = pack_dir(tmp_path, TEXTS)
    (tmp_path / ".env").write_text("this line has no equals sign SECRETISH\nOPENROUTER_API_KEY=k1\n")
    fake = Fake(bodies())
    assert main(["align", str(plan), str(out)], transcriber_factory=factory_for(fake, [])) == 0
    err = capsys.readouterr().err
    assert "SECRETISH" not in err
    assert all(line.startswith("scenevoice align: ") for line in err.splitlines())


def test_injected_fake_never_builds_the_real_transcriber(tmp_path, monkeypatch):
    plan, out, _ = pack_dir(tmp_path, TEXTS)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    real = []
    module = sys.modules["scenevoice.cli.main"]
    monkeypatch.setattr(module, "make_openrouter_transcriber", lambda key: real.append(key))
    fake = Fake(bodies())
    assert main(["align", str(plan), str(out)], transcriber_factory=factory_for(fake, [])) == 0
    assert real == []


def test_default_factory_is_the_real_one_positive_control(tmp_path, monkeypatch):
    plan, out, _ = pack_dir(tmp_path, TEXTS)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    built = []
    fake = Fake(bodies())

    def stand_in(key):
        built.append(key)
        return fake

    monkeypatch.setattr(sys.modules["scenevoice.cli.main"], "make_openrouter_transcriber", stand_in)
    assert main(["align", str(plan), str(out)]) == 0
    assert built == [KEY]


def test_dotenv_logger_is_disabled(tmp_path, monkeypatch):
    import logging

    plan, out, _ = pack_dir(tmp_path, TEXTS)
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    logger = logging.getLogger("dotenv.main")
    monkeypatch.setattr(logger, "disabled", False)
    main(["align", str(plan), str(out)], transcriber_factory=factory_for(Fake(bodies()), []))
    assert logger.disabled is True

