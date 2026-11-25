import os
import sys
from pathlib import Path

import pytest
from keys_helper import CANARY, LOOSE, mode_of, no_warn, posix_only, seed

from scenevoice.keys import read_key_file, set_key
from scenevoice.validation import Violation


def test_set_on_missing_file_creates_it(tmp_path: Path) -> None:
    path = tmp_path / "cfg" / "keys.env"
    assert set_key(path, "ELEVENLABS_API_KEY", "abc", None) is None
    assert path.read_text() == "ELEVENLABS_API_KEY='abc'\n"
    if sys.platform != "win32":
        assert mode_of(path) == 0o600


def test_set_replaces_one_name_and_keeps_the_others(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    seed(path)
    assert set_key(path, "ELEVENLABS_API_KEY", "new", no_warn) is None
    assert read_key_file(path, None) == {"OPENROUTER_API_KEY": "or", "ELEVENLABS_API_KEY": "new"}
    assert path.read_text() == "ELEVENLABS_API_KEY='new'\nOPENROUTER_API_KEY='or'\n"


def test_set_unknown_name_is_refused_and_file_untouched(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    before = seed(path)
    assert set_key(path, "HOME", CANARY, no_warn) == Violation(
        "key-file", "HOME is not a key SceneVoice uses"
    )
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "ELEVENLABS_API_KEY: the value is empty"),
        ("   ", "ELEVENLABS_API_KEY: the value is blank"),
        (f"{CANARY}\nmore", "ELEVENLABS_API_KEY: the value must not contain a line break"),
        (f"{CANARY}\x00", "ELEVENLABS_API_KEY: the value must not contain a NUL character"),
    ],
)
def test_set_bad_value_is_refused_file_unchanged(tmp_path: Path, value: str, message: str) -> None:
    path = tmp_path / "keys.env"
    before = seed(path)
    result = set_key(path, "ELEVENLABS_API_KEY", value, no_warn)
    assert result == Violation("key-file", message)
    assert CANARY not in repr(result)
    assert path.read_bytes() == before


def test_set_drops_blank_values_already_in_the_file(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    seed(path, "OPENROUTER_API_KEY=''\nGOOGLE_CLOUD_PROJECT='p'\nELEVENLABS_API_KEY=\n")
    assert set_key(path, "VERTEX_AUTHORIZATION_KEY", "v", None) is None
    assert path.read_text() == "GOOGLE_CLOUD_PROJECT='p'\nVERTEX_AUTHORIZATION_KEY='v'\n"


def test_set_unreadable_file_fails_and_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    path.write_bytes(b"\xff\xfe" + CANARY.encode())
    before = path.read_bytes()
    result = set_key(path, "ELEVENLABS_API_KEY", "x", None)
    assert result == Violation("key-file", f"could not read key file {path}")
    assert result == read_key_file(path, None)
    assert path.read_bytes() == before


def test_set_malformed_file_fails_and_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    before = seed(path, f"OPENROUTER_API_KEY='or'\nthis is {CANARY}\n")
    result = set_key(path, "ELEVENLABS_API_KEY", "x", None)
    assert result == Violation("key-file", f"key file {path}: line 2 is not NAME=value")
    assert CANARY not in repr(result)
    assert path.read_bytes() == before


def test_set_non_regular_file_fails_and_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    path.mkdir()
    result = set_key(path, "ELEVENLABS_API_KEY", "x", None)
    assert isinstance(result, Violation)
    assert result == read_key_file(path, None)
    assert path.is_dir()
    assert list(path.iterdir()) == []


@posix_only
def test_set_passes_loose_permission_warning_once_and_ends_0600(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    seed(path)
    path.chmod(0o644)
    warnings: list[str] = []
    assert set_key(path, "ELEVENLABS_API_KEY", "x", warnings.append) is None
    assert warnings == [LOOSE.format(path=path)]
    assert mode_of(path) == 0o600


@posix_only
def test_set_write_failure_is_a_path_only_violation(tmp_path: Path) -> None:
    path = tmp_path / "ro" / "keys.env"
    path.parent.mkdir()
    path.parent.chmod(0o500)
    try:
        if os.access(path.parent, os.W_OK):
            pytest.skip("directory permissions not enforced")
        result = set_key(path, "ELEVENLABS_API_KEY", CANARY, None)
    finally:
        path.parent.chmod(0o700)
    assert result == Violation("key-file", f"could not write key file {path}")
    assert CANARY not in repr(result)


def test_set_stores_the_value_exactly_without_stripping(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    assert set_key(path, "ELEVENLABS_API_KEY", " a b ", None) is None
    assert read_key_file(path, None) == {"ELEVENLABS_API_KEY": " a b "}
    assert path.read_bytes() == b"ELEVENLABS_API_KEY=' a b '\n"


def test_set_checks_the_name_before_reading_a_malformed_file(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    before = seed(path, "not a binding\n")
    assert set_key(path, "HOME", "x", None) == Violation(
        "key-file", "HOME is not a key SceneVoice uses"
    )
    assert path.read_bytes() == before
