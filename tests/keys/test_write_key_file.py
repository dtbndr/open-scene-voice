import os
from pathlib import Path

import pytest
from keys_helper import CANARY, mode_of, posix_only

from scenevoice.keys import read_key_file, render_key_file, write_key_file
from scenevoice.validation import Violation

ALL = {
    "OPENROUTER_API_KEY": "or-key",
    "GOOGLE_CLOUD_LOCATION": "us-central1",
    "ELEVENLABS_API_KEY": "el-key",
    "GOOGLE_CLOUD_PROJECT": "proj",
    "VERTEX_AUTHORIZATION_KEY": "vx-key",
}


def test_render_orders_by_key_names_and_quotes() -> None:
    assert render_key_file(ALL) == (
        "GOOGLE_CLOUD_PROJECT='proj'\n"
        "GOOGLE_CLOUD_LOCATION='us-central1'\n"
        "VERTEX_AUTHORIZATION_KEY='vx-key'\n"
        "ELEVENLABS_API_KEY='el-key'\n"
        "OPENROUTER_API_KEY='or-key'\n"
    )


def test_render_skips_absent_and_unknown_names() -> None:
    assert render_key_file({"EXTRA": "x", "ELEVENLABS_API_KEY": "a'b\\c"}) == (
        "ELEVENLABS_API_KEY='a\\'b\\\\c'\n"
    )


@posix_only
def test_write_creates_directory_0700_and_file_0600(tmp_path: Path) -> None:
    path = tmp_path / "newdir" / "keys.env"
    assert write_key_file(path, ALL) is None
    assert mode_of(path) == 0o600
    assert mode_of(path.parent) == 0o700


@posix_only
def test_write_creates_file_0600_even_with_permissive_umask(tmp_path: Path) -> None:
    old = os.umask(0)
    try:
        path = tmp_path / "d" / "keys.env"
        assert write_key_file(path, ALL) is None
    finally:
        os.umask(old)
    assert mode_of(path) == 0o600
    assert mode_of(path.parent) == 0o700


@posix_only
def test_replacing_a_0644_file_gives_0600(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    path.write_text("OLD='x'\n", encoding="utf-8")
    os.chmod(path, 0o644)
    assert write_key_file(path, {"ELEVENLABS_API_KEY": "new"}) is None
    assert mode_of(path) == 0o600
    assert path.read_text(encoding="utf-8") == "ELEVENLABS_API_KEY='new'\n"


@posix_only
def test_replacing_a_symlink_makes_a_regular_file_and_leaves_the_target(tmp_path: Path) -> None:
    target = tmp_path / "target.env"
    target.write_text("KEEP='me'\n", encoding="utf-8")
    link = tmp_path / "keys.env"
    link.symlink_to(target)
    assert write_key_file(link, {"ELEVENLABS_API_KEY": "new"}) is None
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "ELEVENLABS_API_KEY='new'\n"
    assert target.read_text(encoding="utf-8") == "KEEP='me'\n"


def test_success_leaves_only_the_key_file(tmp_path: Path) -> None:
    path = tmp_path / "keys.env"
    assert write_key_file(path, ALL) is None
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keys.env"]


def test_replace_failure_returns_violation_and_removes_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "keys.env"
    path.write_text("OLD='x'\n", encoding="utf-8")

    def boom(src: object, dst: object) -> None:
        raise OSError(f"cannot replace {CANARY}")

    monkeypatch.setattr(os, "replace", boom)
    result = write_key_file(path, {"ELEVENLABS_API_KEY": CANARY})
    assert result == Violation("key-file", f"could not write key file {path}")
    assert result is not None and result.line is None
    assert CANARY not in result.message
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keys.env"]
    assert path.read_text(encoding="utf-8") == "OLD='x'\n"


def test_write_failure_returns_violation_and_removes_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "keys.env"
    real_fdopen = os.fdopen

    def failing_fdopen(fd: int, *args: object, **kwargs: object) -> object:
        os.close(fd)
        raise OSError("disk full")

    monkeypatch.setattr(os, "fdopen", failing_fdopen)
    result = write_key_file(path, {"ELEVENLABS_API_KEY": CANARY})
    monkeypatch.setattr(os, "fdopen", real_fdopen)
    assert result == Violation("key-file", f"could not write key file {path}")
    assert list(tmp_path.iterdir()) == []


def test_unwritable_location_returns_violation(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    path = blocker / "sub" / "keys.env"
    assert write_key_file(path, ALL) == Violation("key-file", f"could not write key file {path}")


def test_round_trip_with_awkward_values(tmp_path: Path) -> None:
    values = dict(ALL)
    values["ELEVENLABS_API_KEY"] = "it's a \\ \"tricky\" $HOME ${X} #not-comment é\\n"
    values["OPENROUTER_API_KEY"] = ""
    path = tmp_path / "keys.env"
    assert write_key_file(path, values) is None
    assert read_key_file(path, None) == values


def test_no_message_carries_a_value(tmp_path: Path) -> None:
    path = tmp_path / "file" / "keys.env"
    (tmp_path / "file").write_text("x", encoding="utf-8")
    result = write_key_file(path, {"ELEVENLABS_API_KEY": CANARY})
    assert result is not None and CANARY not in result.message

