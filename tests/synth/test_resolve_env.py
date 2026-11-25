import os

import pytest
from keys_helper import CANARY, posix_only

from scenevoice.keys import loose_permission_problem, read_key_file
from scenevoice.synth import resolve_env
from scenevoice.validation import Violation

P, L, K = "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "VERTEX_AUTHORIZATION_KEY"


def _env(tmp_path, text: str | bytes | None):
    path = tmp_path / ".env"
    if isinstance(text, bytes):
        path.write_bytes(text)
    elif text is not None:
        path.write_text(text, encoding="utf-8")
    return path


def test_all_present_in_process(tmp_path):
    proc = {P: "p", L: "l", K: "k"}
    assert resolve_env(proc, _env(tmp_path, None)) == proc


def test_process_wins_over_dotenv(tmp_path):
    path = _env(tmp_path, f"{P}=other\n{L}=l2\n{K}=k2\n")
    assert resolve_env({P: "p", L: "l", K: "k"}, path) == {P: "p", L: "l", K: "k"}


def test_missing_name_falls_back_to_dotenv(tmp_path):
    path = _env(tmp_path, f"{L}=l2\n")
    assert resolve_env({P: "p", K: "k"}, path) == {P: "p", L: "l2", K: "k"}


@pytest.mark.parametrize("blank", [" \t\n"])
def test_blank_process_value_falls_back(tmp_path, blank):
    path = _env(tmp_path, f"{P}=fromfile\n")
    result = resolve_env({P: blank, L: "l", K: "k"}, path)
    assert result == {P: "fromfile", L: "l", K: "k"}


def test_missing_list_in_fixed_order(tmp_path):
    path = _env(tmp_path, None)
    assert resolve_env({}, path) == [P, L, K]
    assert resolve_env({L: "l"}, path) == [P, K]
    assert resolve_env({P: "p"}, path) == [L, K]
    assert resolve_env({K: "k"}, path) == [P, L]


def test_missing_dotenv_file_is_empty(tmp_path):
    assert resolve_env({P: "p", L: "l"}, tmp_path / "nope" / ".env") == [K]


def test_quoted_and_export_values_resolve(tmp_path):
    path = _env(tmp_path, f'{P}="my proj"\nexport {L}=us-central1\n{K}=\'k 1\'\n')
    assert resolve_env({}, path) == {P: "my proj", L: "us-central1", K: "k 1"}


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0, reason="permissions not enforced"
)
def test_unreadable_dotenv_is_violation(tmp_path):
    path = _env(tmp_path, f"{P}=topsecret\n")
    path.chmod(0)
    try:
        result = resolve_env({}, path)
    finally:
        path.chmod(0o600)
    assert isinstance(result, Violation)
    assert ".env" in result.message
    assert "topsecret" not in result.message


def test_environ_unchanged_and_no_values_leak(tmp_path, monkeypatch):
    monkeypatch.setenv(P, "env-secret-value")
    before = dict(os.environ)
    path = _env(tmp_path, f"{L}=file-secret-value\n")
    result = resolve_env({}, path)
    assert dict(os.environ) == before
    assert result == [P, K]
    assert "secret" not in repr(result)


def test_names_argument_limits_which_names_are_resolved_and_reported(tmp_path):
    only = ("OPENROUTER_API_KEY",)
    assert resolve_env({}, _env(tmp_path, None), only) == ["OPENROUTER_API_KEY"]
    assert resolve_env({"OPENROUTER_API_KEY": "k"}, _env(tmp_path, None), only) == {
        "OPENROUTER_API_KEY": "k"
    }


P, L, K = "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "VERTEX_AUTHORIZATION_KEY"


def _write(tmp_path, name, text, mode=0o600):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


def _key_env(tmp_path, text=""):
    return _write(tmp_path, ".env", text)


def _keys(tmp_path, text, mode=0o600):
    return _write(tmp_path, "keys.env", text, mode)


def test_process_beats_key_file_beats_dotenv_mixed(tmp_path):
    keys = _keys(tmp_path, f"{P}=kf-p\n{L}=kf-l\n")
    env = _key_env(tmp_path, f"{P}=env-p\n{L}=env-l\n{K}=env-k\n")
    assert resolve_env({P: "proc-p"}, env, key_file=keys) == {P: "proc-p", L: "kf-l", K: "env-k"}


def test_blank_process_value_falls_to_key_file(tmp_path):
    keys = _keys(tmp_path, f"{P}=kf-p\n")
    assert resolve_env({P: "  "}, _key_env(tmp_path), (P,), key_file=keys) == {P: "kf-p"}


def test_missing_names_listed_when_nothing_supplies(tmp_path):
    assert resolve_env({}, _key_env(tmp_path), (P, L), key_file=_keys(tmp_path, "")) == [P, L]


def test_broken_key_file_fails_even_when_process_supplies_everything(tmp_path):
    keys = _keys(tmp_path, f"this is not a binding {CANARY}\n")
    result = resolve_env({P: "p", L: "l", K: "k"}, _key_env(tmp_path), key_file=keys)
    assert isinstance(result, Violation)
    assert result == read_key_file(keys, None)
    assert CANARY not in result.message


def test_key_file_violation_returned_before_dotenv_is_read(tmp_path):
    keys = _keys(tmp_path, "garbage line\n")
    bad_env = tmp_path / ".env"
    bad_env.write_bytes(b"\xff\xfe\x00bad")
    result = resolve_env({}, bad_env, (P,), key_file=keys)
    assert isinstance(result, Violation)
    assert result == read_key_file(keys, None)


@posix_only
def test_loose_permission_warning_emitted_even_when_not_needed(tmp_path):
    keys = _keys(tmp_path, f"{P}=kf\n", mode=0o644)
    seen: list[str] = []
    result = resolve_env({P: "p"}, _key_env(tmp_path), (P,), key_file=keys, warn=seen.append)
    assert result == {P: "p"}
    assert seen == [loose_permission_problem(keys)]
    assert seen[0] is not None


def test_canary_values_never_in_violation_messages(tmp_path):
    keys = _keys(tmp_path, f"{P}={CANARY}\nbroken {CANARY}\n")
    result = resolve_env({K: CANARY}, _key_env(tmp_path, f"{L}={CANARY}\n"), key_file=keys)
    assert isinstance(result, Violation)
    assert CANARY not in result.message
