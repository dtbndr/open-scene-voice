import os
import sys

import pytest

from scenevoice.synth import ENV_NAMES, resolve_env
from scenevoice.validation import Violation

P, L, K = "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "VERTEX_AUTHORIZATION_KEY"


def _env(tmp_path, text: str | bytes | None):
    path = tmp_path / ".env"
    if isinstance(text, bytes):
        path.write_bytes(text)
    elif text is not None:
        path.write_text(text, encoding="utf-8")
    return path


def test_env_names_order():
    assert ENV_NAMES == (P, L, K)


def test_all_present_in_process(tmp_path):
    proc = {P: "p", L: "l", K: "k"}
    assert resolve_env(proc, _env(tmp_path, None)) == proc


def test_process_wins_over_dotenv(tmp_path):
    path = _env(tmp_path, f"{P}=other\n{L}=l2\n{K}=k2\n")
    assert resolve_env({P: "p", L: "l", K: "k"}, path) == {P: "p", L: "l", K: "k"}


def test_missing_name_falls_back_to_dotenv(tmp_path):
    path = _env(tmp_path, f"{L}=l2\n")
    assert resolve_env({P: "p", K: "k"}, path) == {P: "p", L: "l2", K: "k"}


@pytest.mark.parametrize("blank", ["", " ", " \t\n"])
def test_blank_process_value_falls_back(tmp_path, blank):
    path = _env(tmp_path, f"{P}=fromfile\n")
    result = resolve_env({P: blank, L: "l", K: "k"}, path)
    assert result == {P: "fromfile", L: "l", K: "k"}


def test_whitespace_only_dotenv_value_does_not_count(tmp_path):
    path = _env(tmp_path, f"{P}='   '\n")
    assert resolve_env({L: "l", K: "k"}, path) == [P]


def test_blank_in_both_is_missing(tmp_path):
    path = _env(tmp_path, f"{P}=\n")
    assert resolve_env({P: "  ", L: "l", K: "k"}, path) == [P]


def test_missing_list_in_fixed_order(tmp_path):
    path = _env(tmp_path, None)
    assert resolve_env({}, path) == [P, L, K]
    assert resolve_env({L: "l"}, path) == [P, K]
    assert resolve_env({P: "p"}, path) == [L, K]
    assert resolve_env({K: "k"}, path) == [P, L]


def test_missing_dotenv_file_is_empty(tmp_path):
    assert resolve_env({P: "p", L: "l"}, tmp_path / "nope" / ".env") == [K]


def test_bare_name_line_is_blank(tmp_path):
    path = _env(tmp_path, f"{P}\n")
    assert resolve_env({L: "l", K: "k"}, path) == [P]


def test_quoted_and_export_values_resolve(tmp_path):
    path = _env(tmp_path, f'{P}="my proj"\nexport {L}=us-central1\n{K}=\'k 1\'\n')
    assert resolve_env({}, path) == {P: "my proj", L: "us-central1", K: "k 1"}


def test_values_returned_unmodified(tmp_path):
    result = resolve_env({P: "  p  ", L: "l", K: "k"}, _env(tmp_path, None))
    assert result[P] == "  p  "


def test_interpolation_not_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("SOME_NAME", "expanded")
    path = _env(tmp_path, f"{P}=${{SOME_NAME}}\n")
    result = resolve_env({L: "l", K: "k"}, path)
    assert result[P] == "${SOME_NAME}"


def test_undecodable_dotenv_is_violation(tmp_path):
    path = _env(tmp_path, b"GOOGLE_CLOUD_PROJECT=\xff\xfesecretbytes\n")
    result = resolve_env({}, path)
    assert isinstance(result, Violation)
    assert ".env" in result.message
    assert "secretbytes" not in result.message


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


def test_oserror_from_reader_is_violation(tmp_path, monkeypatch):
    module = sys.modules["scenevoice.synth.resolve_env"]
    calls = []

    def fake(path, **kwargs):
        calls.append(path)
        raise OSError("boom topsecret")

    monkeypatch.setattr(module, "dotenv_values", fake)
    result = resolve_env({}, _env(tmp_path, None))
    assert calls, "fake reader was not called"
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
