import builtins
import io
import sys

import pytest

from scenevoice.cli.main import _build_parser, main


class Boom:
    """A stdin that fails the test if it is read."""

    def isatty(self):
        return False

    def read(self):
        raise AssertionError("stdin must not be read")

    @property
    def buffer(self):
        raise AssertionError("stdin must not be read")


def usage_error(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["align", *argv])
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "usage" in captured.err.lower()
    return captured.err


def align_parser():
    sub = next(a for a in _build_parser()._actions if a.dest == "command")
    return sub.choices["align"]


def test_two_positionals_parse_as_plan_then_dir():
    args = _build_parser().parse_args(["align", "plan.json", "out"])
    assert (args.plan, args.dir) == ("plan.json", "out")


def test_one_positional_is_dir_and_plan_is_stdin():
    args = _build_parser().parse_args(["align", "out"])
    assert (args.plan, args.dir) == (None, "out")


def test_missing_dir_touches_no_io(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", Boom())
    err = usage_error([], capsys)
    assert "[PLAN] DIR" in err


def test_extra_positionals_touch_no_io(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", Boom())
    opened = []
    real_open = builtins.open

    def spy(target, *a, **k):
        opened.append(str(target))
        return real_open(target, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    usage_error(["nope-plan.json", "nope-dir", "extra"], capsys)
    assert not [p for p in opened if "nope" in p]
    assert not (tmp_path / "nope-dir").exists()


def test_open_spy_positive_control(tmp_path, monkeypatch):
    opened = []
    real_open = builtins.open

    def spy(target, *a, **k):
        opened.append(str(target))
        return real_open(target, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    (tmp_path / "x").write_text("1")
    with open(tmp_path / "x"):
        pass
    assert any(p.endswith("/x") for p in opened)


@pytest.mark.parametrize(
    "option",
    [["--model", "m"], ["--language", "en"], ["--base-url", "u"], ["--scene", "1"], ["--bogus"]],
)
def test_unrecognised_options_are_usage_errors(option, capsys):
    usage_error([*option, "out"], capsys)


def test_abbreviated_help_is_not_accepted(capsys):
    usage_error(["--he", "out"], capsys)


def test_usage_text_shows_plan_dir():
    usage = align_parser().format_usage()
    assert usage.strip() == "usage: scenevoice align [-h] [PLAN] DIR"


def test_help_names_the_hosted_call_and_key(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["align", "--help"])
    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "[PLAN] DIR" in out
    assert "OPENROUTER_API_KEY" in out
    assert "hosted" in out
    assert "line_timings.json" in out
    assert "synth_record.json" in out
    flat = " ".join(out.split())
    assert "one hosted transcription call per scene" not in flat
    assert "one hosted OpenRouter transcription call per scene" not in flat


def test_top_level_help_lists_align(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "align" in capsys.readouterr().out


class Tty(io.StringIO):
    def isatty(self):
        return True


def test_terminal_stdin_without_plan_exits_1_before_directory_check(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", Tty())

    def never(key):
        raise AssertionError("factory must not be built")

    code = main(["align", "missing-dir"], transcriber_factory=never)
    err = capsys.readouterr().err
    assert code == 1
    assert "FAIL" in err and "terminal" in err
    assert "missing-dir" not in err
