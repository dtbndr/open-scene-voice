import builtins
import contextlib
import io
import os
import pathlib

import pytest

from scenevoice.cli.main import _build_parser, main


class PathSpy:
    """Records every path touched through open/io.open/Path.open/os.stat-family calls."""

    def __init__(self):
        self.touched = []

    def record(self, target):
        if isinstance(target, (str, bytes, os.PathLike)):
            self.touched.append(os.path.abspath(os.fsdecode(target)))

    def touched_any(self, *paths):
        wanted = {os.path.abspath(str(p)) for p in paths}
        return sorted(wanted & set(self.touched))


@pytest.fixture
def spy(tmp_path, monkeypatch):
    """Isolated cwd and a PathSpy; patches are applied only inside spy.watching()."""
    monkeypatch.chdir(tmp_path)
    return PathSpy()


@contextlib.contextmanager
def watching(spy):
    patches = []

    def wrap(owner, name):
        real = getattr(owner, name)

        def wrapper(target, *args, **kwargs):
            spy.record(target)
            return real(target, *args, **kwargs)

        patches.append((owner, name, real))
        setattr(owner, name, wrapper)

    for owner, name in [
        (builtins, "open"), (io, "open"), (os, "stat"), (os, "lstat"),
        (os, "listdir"), (os, "scandir"),
    ]:
        wrap(owner, name)
    real_path_open = pathlib.Path.open

    def path_open(self, *args, **kwargs):
        spy.record(self)
        return real_path_open(self, *args, **kwargs)

    patches.append((pathlib.Path, "open", real_path_open))
    pathlib.Path.open = path_open
    try:
        yield
    finally:
        for owner, name, real in reversed(patches):
            setattr(owner, name, real)


def run_usage(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["pack", *argv])
    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "usage" in captured.err.lower()
    return captured.err


def test_spy_positive_control_sees_plain_open_path_read_and_stat(spy, tmp_path):
    (tmp_path / "a.json").write_text("{}")
    with watching(spy):
        with open("a.json"):
            pass
        pathlib.Path("b.json").exists()
        with pytest.raises(FileNotFoundError):
            pathlib.Path("c.json").read_bytes()
        os.stat("a.json")
        os.listdir(".")
    assert spy.touched_any("a.json", "b.json", "c.json") == sorted(
        os.path.abspath(n) for n in ("a.json", "b.json", "c.json"))


def test_spy_flags_a_plan_opened_before_the_usage_check(spy, tmp_path):
    def opens_plan_first(argv):
        open(argv[1]).close()  # the bug a future dispatch could introduce
        return main(argv)

    plan = tmp_path / "plan.json"
    plan.write_text("{}")
    with watching(spy), pytest.raises(SystemExit):
        opens_plan_first(["pack", str(plan), "d", "extra"])
    assert spy.touched_any(plan) == [str(plan.resolve())]


def test_no_arguments(capsys):
    run_usage([], capsys)


def test_third_positional(capsys):
    run_usage(["plan.json", "out", "extra"], capsys)


def test_unrecognised_option(capsys):
    run_usage(["--bogus", "out"], capsys)


def test_out_option_is_not_accepted(capsys):
    run_usage(["--out", "x", "dir"], capsys)


@pytest.mark.parametrize("argv", [["--he"], ["--hel", "out"]])
def test_abbreviated_help_is_rejected_not_a_prefix_match(argv, capsys):
    # --help is the only long option; an abbreviation must not match it.
    run_usage(argv, capsys)


def test_unknown_option_with_two_positionals(capsys):
    run_usage(["plan.json", "out", "--o"], capsys)


def test_usage_error_with_missing_plan_and_dir_touches_no_path(spy, tmp_path, capsys):
    plan, directory = tmp_path / "missing-plan.json", tmp_path / "missing-dir"
    with watching(spy):
        run_usage([str(plan), str(directory), "third"], capsys)
    assert spy.touched_any(plan, directory) == []


def test_usage_line_reads_plan_dir_without_repetition(capsys):
    err = run_usage([], capsys)
    usage = err.split("scenevoice pack:")[0]
    assert "[PLAN] DIR" in usage
    assert "..." not in usage


def test_pack_help_exits_zero_on_stdout(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["pack", "--help"])
    assert exc.value.code == 0
    assert "DIR" in capsys.readouterr().out


def parse(argv):
    return _build_parser().parse_args(["pack", *argv])


def test_one_positional_is_dir_and_plan_is_unset():
    args = parse(["out"])
    assert args.command == "pack"
    assert args.dir == "out"
    assert args.plan is None


def test_two_positionals_are_plan_then_dir():
    args = parse(["plan.json", "out"])
    assert (args.plan, args.dir) == ("plan.json", "out")


def test_double_dash_lets_a_dash_leading_dir_through():
    args = parse(["--", "-weird-dir"])
    assert args.dir == "-weird-dir"
    assert args.plan is None


def test_double_dash_with_plan_and_dash_leading_dir():
    args = parse(["plan.json", "--", "-weird-dir"])
    assert (args.plan, args.dir) == ("plan.json", "-weird-dir")
