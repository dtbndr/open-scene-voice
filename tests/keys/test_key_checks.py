import io
import os

import pytest
from dotenv.parser import parse_stream
from keys_helper import CANARY, posix_only
from paths_helper import REPO_ROOT

from scenevoice.keys import missing_key_message
from scenevoice.keys.check_key_value import check_key_value
from scenevoice.keys.key_names import KEY_NAMES, NON_SECRET_NAMES
from scenevoice.keys.loose_permission_problem import loose_permission_problem
from scenevoice.keys.quote_key_value import quote_key_value

NAME = "GOOGLE_CLOUD_PROJECT"


def test_normal_key_is_accepted():
    assert check_key_value("ELEVENLABS_API_KEY", "sk_abc123-XYZ") is None


def test_value_with_inner_spaces_and_symbols_is_accepted():
    assert check_key_value(NAME, "a b #c $d 'e' \"f\" \\g é") is None


def test_empty_is_refused():
    assert check_key_value(NAME, "") == "GOOGLE_CLOUD_PROJECT: the value is empty"


@pytest.mark.parametrize("blank", [" ", "   ", "\t", " \t ", " ", " "])
def test_blank_is_refused(blank):
    assert check_key_value(NAME, blank) == "GOOGLE_CLOUD_PROJECT: the value is blank"


@pytest.mark.parametrize("bad", ["\n", "\r\n"])
def test_line_break_is_refused_even_alone(bad):
    assert check_key_value(NAME, bad) == "GOOGLE_CLOUD_PROJECT: the value must not contain a line break"


@pytest.mark.parametrize("pattern", [f"{CANARY}\n", f"{CANARY}\r{CANARY}"])
def test_embedded_line_break_is_refused_without_echoing_the_value(pattern):
    message = check_key_value("ELEVENLABS_API_KEY", pattern)
    assert message == "ELEVENLABS_API_KEY: the value must not contain a line break"
    assert CANARY not in message


@pytest.mark.parametrize("pattern", [f"{CANARY}\x00"])
def test_nul_is_refused_without_echoing_the_value(pattern):
    message = check_key_value("OPENROUTER_API_KEY", pattern)
    assert message == "OPENROUTER_API_KEY: the value must not contain a NUL character"
    assert CANARY not in message


@pytest.mark.parametrize("value", [" ", f"{CANARY}\n", f"{CANARY}\x00"])
def test_no_message_contains_the_value(value):
    message = check_key_value(NAME, value)
    assert message is not None
    assert CANARY not in message


# One value per quoting class; the stored key must read back exactly through the
# dotenv parser (P0/P1: a corrupted key makes every paid call fail).
AWKWARD = [
    "plain",
    " leading",
    "trailing ",
    "a#b",
    "$HOME",
    "${VAR}",
    "a=b",
    "it's",
    '"double"',
    "back\\slash",
    "ends\\",
    "a\\nb",
    "\\'",
    "naïve ключ 鍵 🔑",
]


@pytest.mark.parametrize("value", AWKWARD)
def test_quote_round_trips_exactly_through_parse_stream(value):
    token = quote_key_value(value)
    bindings = list(parse_stream(io.StringIO(f"{NAME}={token}\n")))
    assert len(bindings) == 1
    assert not bindings[0].error
    assert (bindings[0].key, bindings[0].value) == (NAME, value)
    text = f"A=1\n{NAME}={token}\nB=2"
    got = {b.key: b.value for b in parse_stream(io.StringIO(text))}
    assert got == {"A": "1", NAME: value, "B": "2"}


def test_quote_exact_tokens():
    assert quote_key_value("plain") == "'plain'"
    assert quote_key_value("it's") == "'it\\'s'"
    assert quote_key_value("a\\b") == "'a\\\\b'"


def test_key_names_equal_env_example_names_in_file_order():
    lines = (REPO_ROOT / ".env.example").read_text().splitlines()
    parsed = [ln.split("=", 1)[0] for ln in lines if ln and not ln.startswith("#")]
    assert list(KEY_NAMES) == parsed
    assert len(KEY_NAMES) == 5


def test_non_secret_names_are_project_and_location_only():
    assert NON_SECRET_NAMES == ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION")
    assert all(name in KEY_NAMES for name in NON_SECRET_NAMES)


def test_one_name_with_key_file():
    assert missing_key_message(["A_KEY"], "/h/keys.env") == (
        'Missing: A_KEY. Add it with "scenevoice keys set A_KEY", or put it in /h/keys.env.'
    )


def test_several_names_with_key_file_uses_first_name_in_command():
    assert missing_key_message(["A_KEY", "B_KEY"], "/h/keys.env") == (
        'Missing: A_KEY, B_KEY. Add them with "scenevoice keys set A_KEY", or put them in /h/keys.env.'
    )


def test_one_name_without_key_file():
    assert missing_key_message(["A_KEY"], None) == 'Missing: A_KEY. Add it with "scenevoice keys set A_KEY".'


def test_several_names_without_key_file():
    assert missing_key_message(["A_KEY", "B_KEY"], None) == (
        'Missing: A_KEY, B_KEY. Add them with "scenevoice keys set A_KEY".'
    )


def test_path_object_is_rendered_as_given(tmp_path):
    path = tmp_path / "k.env"
    assert missing_key_message(["A_KEY"], path).endswith(f"put it in {path}.")


@posix_only
@pytest.mark.parametrize("mode", [0o640, 0o604])
def test_group_or_other_access_is_reported_with_exact_text(tmp_path, mode):
    f = tmp_path / "keys.env"
    f.write_text("A=b\n")
    f.chmod(mode)
    assert loose_permission_problem(f) == f"key file {f} can be read by other users; run chmod 600 {f}"


@posix_only
@pytest.mark.parametrize("mode", [0o600])
def test_owner_only_is_fine(tmp_path, mode):
    f = tmp_path / "keys.env"
    f.write_text("A=b\n")
    f.chmod(mode)
    assert loose_permission_problem(f) is None


def test_missing_file_is_left_to_the_read_error(tmp_path):
    assert loose_permission_problem(tmp_path / "nope") is None


def test_windows_never_reports(tmp_path, monkeypatch):
    f = tmp_path / "keys.env"
    f.write_text("A=b\n")
    if os.name != "nt":
        f.chmod(0o666)
    monkeypatch.setattr(os, "name", "nt")
    assert loose_permission_problem(f) is None
