import os
import sys
from pathlib import Path

import pytest
from keys_helper import CANARY, LOOSE, mode_of, no_warn, posix_only, seed

from scenevoice.keys import read_key_file, remove_key
from scenevoice.validation import Violation


def test_remove_saved_name_keeps_the_others(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    seed(path)
    assert remove_key(path, "ELEVENLABS_API_KEY", no_warn) == "removed"
    assert path.read_text() == "OPENROUTER_API_KEY='or'\n"


def test_remove_last_name_leaves_an_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    seed(path, "# note\nOTHER=1\nOPENROUTER_API_KEY='or'\n")
    assert remove_key(path, "OPENROUTER_API_KEY", None) == "removed"
    assert path.exists()
    assert path.read_bytes() == b""
    if sys.platform != "win32":
        assert mode_of(path) == 0o600


def test_remove_absent_name_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    before = seed(path)
    os.utime(path, (1_000_000_000, 1_000_000_000))
    assert remove_key(path, "GOOGLE_CLOUD_PROJECT", no_warn) == "absent"
    assert path.read_bytes() == before
    assert os.stat(path).st_mtime == 1_000_000_000


def test_remove_on_missing_file_is_absent_and_creates_nothing(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "keys.env"
    assert remove_key(path, "ELEVENLABS_API_KEY", None) == "absent"
    assert not path.parent.exists()


def test_remove_blank_entry_counts_as_absent_and_file_is_untouched(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    before = seed(path, "ELEVENLABS_API_KEY=''\n# keep me\nOPENROUTER_API_KEY='or'\n")
    assert remove_key(path, "ELEVENLABS_API_KEY", None) == "absent"
    assert path.read_bytes() == before


def test_remove_unknown_name_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    before = seed(path)
    assert remove_key(path, "HOME", no_warn) == Violation(
        "key-file", "HOME is not a key SceneVoice uses"
    )
    assert path.read_bytes() == before


def test_remove_unreadable_file_fails_and_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    path.write_bytes(b"\xff\xfe" + CANARY.encode())
    before = path.read_bytes()
    result = remove_key(path, "ELEVENLABS_API_KEY", None)
    assert result == Violation("key-file", f"could not read key file {path}")
    assert path.read_bytes() == before


def test_remove_malformed_file_fails_and_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    before = seed(path, f"ELEVENLABS_API_KEY='el'\nthis is {CANARY}\n")
    result = remove_key(path, "ELEVENLABS_API_KEY", None)
    assert result == Violation("key-file", f"key file {path}: line 2 is not NAME=value")
    assert CANARY not in repr(result)
    assert path.read_bytes() == before


def test_remove_non_regular_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    path.mkdir()
    result = remove_key(path, "ELEVENLABS_API_KEY", None)
    assert isinstance(result, Violation)
    assert result == read_key_file(path, None)
    assert path.is_dir()


@posix_only
def test_remove_passes_loose_permission_warning_once_and_ends_0600(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    seed(path)
    path.chmod(0o644)
    warnings: list[str] = []
    assert remove_key(path, "ELEVENLABS_API_KEY", warnings.append) == "removed"
    assert warnings == [LOOSE.format(path=path)]
    assert mode_of(path) == 0o600


@posix_only
def test_remove_write_failure_is_a_path_only_violation(tmp_path: Path) -> None:
    path = tmp_path / "ro" / "keys.env"
    path.parent.mkdir()
    seed(path, f"ELEVENLABS_API_KEY='{CANARY}'\n")
    path.parent.chmod(0o500)
    try:
        if os.access(path.parent, os.W_OK):
            pytest.skip("directory permissions not enforced")
        result = remove_key(path, "ELEVENLABS_API_KEY", None)
    finally:
        path.parent.chmod(0o700)
    assert result == Violation("key-file", f"could not write key file {path}")
    assert CANARY not in repr(result)

