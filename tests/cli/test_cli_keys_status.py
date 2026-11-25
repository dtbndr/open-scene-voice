import json
import logging
import sys

import pytest
from keys_helper import CANARY

from scenevoice.cli.main import main
from scenevoice.keys.key_status import key_status

NAMES = (
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "VERTEX_AUTHORIZATION_KEY",
    "ELEVENLABS_API_KEY",
    "OPENROUTER_API_KEY",
)


def _status(capsys):
    assert main(["keys", "status"]) == 0
    return capsys.readouterr()


def test_exact_stdout_shape_and_order(key_file, key_path, capsys):
    path = key_file(
        f"GOOGLE_CLOUD_PROJECT=my-proj\nVERTEX_AUTHORIZATION_KEY={CANARY}\nOPENROUTER_API_KEY={CANARY}\n"
    )
    out, err = _status(capsys)
    assert out == (
        '{"path": "' + str(path) + '", "keys": {'
        '"GOOGLE_CLOUD_PROJECT": {"saved": true, "value": "my-proj"}, '
        '"GOOGLE_CLOUD_LOCATION": {"saved": false}, '
        '"VERTEX_AUTHORIZATION_KEY": {"saved": true}, '
        '"ELEVENLABS_API_KEY": {"saved": false}, '
        '"OPENROUTER_API_KEY": {"saved": true}}}\n'
    )
    assert err == ""
    assert CANARY not in out + err


def test_missing_file_all_not_saved(key_path, capsys):
    assert not key_path.exists()
    out, err = _status(capsys)
    assert json.loads(out) == {"path": str(key_path), "keys": {n: {"saved": False} for n in NAMES}}
    assert err == ""


def test_blank_counts_as_not_saved(key_file, capsys):
    key_file(
        'GOOGLE_CLOUD_PROJECT=\nGOOGLE_CLOUD_LOCATION="   "\nELEVENLABS_API_KEY=" "\n'
        f"OPENROUTER_API_KEY={CANARY}\n"
    )
    out, err = _status(capsys)
    assert json.loads(out)["keys"] == {
        "GOOGLE_CLOUD_PROJECT": {"saved": False},
        "GOOGLE_CLOUD_LOCATION": {"saved": False},
        "VERTEX_AUTHORIZATION_KEY": {"saved": False},
        "ELEVENLABS_API_KEY": {"saved": False},
        "OPENROUTER_API_KEY": {"saved": True},
    }
    assert err == ""


@pytest.mark.parametrize("text", [None, "GOOGLE_CLOUD_LOCATION=file-loc\n"], ids=["no-file", "one-name"])
def test_status_ignores_environment_and_dotenv(key_file, key_path, tmp_path, monkeypatch, capsys, text):
    if text is not None:
        key_file(text)
    for name in NAMES:
        monkeypatch.setenv(name, f"ENV-{CANARY}")
    (tmp_path / ".env").write_text("".join(f"{n}=DOTENV-{CANARY}\n" for n in NAMES), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    out, err = _status(capsys)
    expected = {n: {"saved": False} for n in NAMES}
    if text is not None:
        expected["GOOGLE_CLOUD_LOCATION"] = {"saved": True, "value": "file-loc"}
    assert json.loads(out)["keys"] == expected
    assert err == ""
    assert CANARY not in out + err


def test_non_ascii_value_is_not_escaped(key_file, capsys):
    key_file("GOOGLE_CLOUD_PROJECT=projé-ü\n")
    out, _ = _status(capsys)
    assert '"value": "projé-ü"' in out
    assert "\\u" not in out


@pytest.mark.parametrize("breaker", ["malformed", "directory"])
def test_unusable_file_fails_with_empty_stdout(key_file, capsys, breaker):
    path = key_file(f"OPENROUTER_API_KEY={CANARY}\nthis is {CANARY} not valid\n")
    if breaker == "directory":
        path.unlink()
        path.mkdir()
    assert main(["keys", "status"]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith("scenevoice keys: FAIL key file ")
    assert str(path) in err
    assert CANARY not in out + err


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_loose_mode_notes_once(key_file, capsys):
    path = key_file(f"OPENROUTER_API_KEY={CANARY}\n", mode=0o644)
    out, err = _status(capsys)
    assert err == (
        f"scenevoice keys: NOTE key file {path} can be read by other users; run chmod 600 {path}\n"
    )
    assert json.loads(out)["keys"]["OPENROUTER_API_KEY"] == {"saved": True}
    assert CANARY not in out + err


def test_key_status_pure_function():
    raw = {
        "GOOGLE_CLOUD_LOCATION": "us-central1",
        "ELEVENLABS_API_KEY": CANARY,
        "GOOGLE_CLOUD_PROJECT": "  ",
        "VERTEX_AUTHORIZATION_KEY": "",
    }
    result = key_status(raw)
    assert list(result) == list(NAMES)
    assert result == {
        "GOOGLE_CLOUD_PROJECT": {"saved": False},
        "GOOGLE_CLOUD_LOCATION": {"saved": True, "value": "us-central1"},
        "VERTEX_AUTHORIZATION_KEY": {"saved": False},
        "ELEVENLABS_API_KEY": {"saved": True},
        "OPENROUTER_API_KEY": {"saved": False},
    }


@pytest.fixture
def dotenv_logger():
    logger = logging.getLogger("dotenv.main")
    saved = (logger.disabled, logger.level)
    logger.disabled = False
    logger.setLevel(logging.NOTSET)
    yield logger
    logger.disabled, level = saved
    logger.setLevel(level)


def test_status_disables_dotenv_logger(key_path, dotenv_logger):
    assert main(["keys", "status"]) == 0
    assert dotenv_logger.disabled is True
