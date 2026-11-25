import sys

import pytest

from scenevoice.cli.main import main
from scenevoice.web import DEFAULT_PORT


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake_run_web(**options):
        recorded.append(options)
        return 0

    monkeypatch.setattr(sys.modules["scenevoice.cli.web"], "run_web", fake_run_web)
    return recorded


def opener(link):
    raise AssertionError("the opener must not run in parser tests")


def test_top_level_help_lists_web(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "web" in capsys.readouterr().out


def test_web_help_shows_exactly_port_and_no_open(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["web", "--help"])
    out = capsys.readouterr().out
    assert exc.value.code == 0
    flags = {word.rstrip(",") for word in out.split() if word.startswith("--")}
    assert flags == {"--help", "--port", "--no-open"}


def test_defaults_and_injected_opener_reach_run_web(calls):
    assert main(["web"], browser_opener=opener) == 0
    assert len(calls) == 1
    assert (calls[0]["port"], calls[0]["no_open"], calls[0]["opener"]) == (DEFAULT_PORT, False, opener)


def test_flags_reach_run_web(calls):
    assert main(["web", "--port", "5000", "--no-open"], browser_opener=opener) == 0
    assert (calls[0]["port"], calls[0]["no_open"]) == (5000, True)


@pytest.mark.parametrize("value", ["1023", "abc"])
def test_a_bad_port_is_a_usage_error(calls, capsys, value):
    with pytest.raises(SystemExit) as exc:
        main(["web", "--port", value], browser_opener=opener)
    assert exc.value.code == 2
    assert calls == [] and "usage" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("value", ["1024", "65535"])
def test_the_port_range_limits_are_accepted(calls, value):
    assert main(["web", "--port", value], browser_opener=opener) == 0
    assert calls[0]["port"] == int(value)


@pytest.mark.parametrize("argv", [["web", "extra"], ["web", "--bogus"]])
def test_unknown_flags_and_arguments_are_refused(calls, argv):
    with pytest.raises(SystemExit) as exc:
        main(argv, browser_opener=opener)
    assert exc.value.code == 2
    assert calls == []


def test_the_effective_key_file_path_reaches_run_web_absolute(calls, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCENEVOICE_KEYS_FILE", "rel/keys.env")
    assert main(["web"], browser_opener=opener) == 0
    assert calls[0]["key_file"] == tmp_path / "rel" / "keys.env"
