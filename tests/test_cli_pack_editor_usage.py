import io
from pathlib import Path

import pytest

from scenevoice.cli.main import _build_parser, main


class ForbiddenStdin(io.StringIO):
    def read(self, *args, **kwargs):
        raise AssertionError("stdin was read")

    def readline(self, *args, **kwargs):
        raise AssertionError("stdin was read")


def parse(argv):
    return _build_parser().parse_args(["pack", *argv])


def usage_error(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["pack", *argv])
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "resolve" in captured.err
    return captured.err


def test_editor_before_the_positionals():
    args = parse(["--editor", "resolve", "out"])
    assert (args.editor, args.plan, args.dir) == ("resolve", None, "out")


def test_editor_after_the_positionals():
    args = parse(["out", "--editor", "resolve"])
    assert (args.editor, args.dir) == ("resolve", "out")


def test_editor_with_equals_and_plan():
    args = parse(["--editor=resolve", "plan.json", "out"])
    assert (args.editor, args.plan, args.dir) == ("resolve", "plan.json", "out")


def test_repeated_editor_last_wins():
    assert parse(["--editor", "resolve", "--editor", "resolve", "out"]).editor == "resolve"


def test_without_the_flag_editor_is_none():
    assert parse(["out"]).editor is None
    assert parse(["plan.json", "out"]).editor is None


@pytest.mark.parametrize(
    "argv",
    [
        ["out", "--editor"],
        ["out", "--editor", ""],
        ["--editor", "Resolve", "out"],
        ["--editor", "premiere", "out"],
        ["--editor", "resolve ", "out"],
        ["--editor", "resolve"],
    ],
)
def test_bad_editor_usage_is_exit_2_naming_resolve(argv, capsys):
    usage_error(argv, capsys)


def test_usage_error_happens_before_any_io(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", ForbiddenStdin())
    plan = tmp_path / "missing_plan.json"
    out = tmp_path / "not_created"
    usage_error(["--editor", "premiere", str(plan), str(out)], capsys)
    assert not plan.exists()
    assert not Path(out).exists()


def test_pack_usage_line_shows_the_closed_choice(capsys):
    err = usage_error(["--editor", "nope", "out"], capsys)
    assert "[--editor {resolve}] [PLAN] DIR" in err


def test_pack_help_lists_editor_and_resolve(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["pack", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert exc.value.code == 0
    assert "--editor" in out
    assert "resolve" in out


def test_abbreviated_editor_option_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["pack", "--edit", "resolve", "out"])
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "--edit" in captured.err
