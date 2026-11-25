import os
import sys
from pathlib import Path

import pytest

from scenevoice.web import (
    absolute_keys_file,
    audio_file_name,
    build_allowlist,
    exact_entry,
    is_key_file,
    is_project_id,
    key_file_overlap,
    slugify_name,
    spelling_conflict,
)


@pytest.mark.parametrize("name", ["001.wav", "1000.wav"])
def test_a_synth_wav_name_is_accepted(name):
    assert audio_file_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "01.wav",
        ".write-001.wav.tmp",
        "../001.wav",
        "001/001.wav",
        "",
    ],
)
# Read outside the project: the name becomes a path under audio/, so only NNN.wav passes.
def test_anything_else_is_refused(name):
    assert audio_file_name(name) is False


@pytest.mark.parametrize("value", ["a", "my-video", "a" * 64])
def test_valid_ids_pass(value):
    assert is_project_id(value)


# Outside the project or workspace: an id is a folder name, so path shapes must fail.
@pytest.mark.parametrize("value", ["", "-a", "A", "a.b", "..", "a/b", "%2e%2e", "a\\b", "a\n", "a" * 65])
def test_everything_else_is_refused(value):
    assert not is_project_id(value)


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("My Video", "my-video"),
        ("Café Münster", "cafe-munster"),
        ("", "untitled"),
    ],
)
def test_slug_examples(name, slug):
    assert slugify_name(name) == slug


def test_cap_is_64_and_trims_after_the_cut():
    assert slugify_name("a" * 100) == "a" * 64
    assert slugify_name("a" * 63 + " " + "b" * 10) == "a" * 63


# Read/write outside the workspace: a slug is a folder name and never a path.
@pytest.mark.parametrize("name", ["x" * 200, "..", "A/B\\C"])
def test_output_always_satisfies_is_project_id(name):
    assert is_project_id(slugify_name(name))


def test_only_regular_nested_files_become_entries(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_bytes(b"home")
    (tmp_path / "_app" / "immutable").mkdir(parents=True)
    (tmp_path / "_app" / "immutable" / "a.js").write_bytes(b"js")
    (tmp_path / "empty_dir").mkdir()
    assert build_allowlist(tmp_path) == {"index.html": b"home", "_app/immutable/a.js": b"js"}


def test_dotfiles_and_dot_directories_are_skipped(tmp_path: Path) -> None:
    (tmp_path / ".DS_Store").write_bytes(b"x")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "a.js").write_bytes(b"x")
    (tmp_path / "ok.txt").write_bytes(b"ok")
    assert set(build_allowlist(tmp_path)) == {"ok.txt"}


def test_a_symlink_to_a_file_or_directory_outside_is_not_an_entry(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"secret")
    root = tmp_path / "static"
    root.mkdir()
    (root / "ok.txt").write_bytes(b"ok")
    os.symlink(outside / "secret.txt", root / "link.txt")
    os.symlink(outside, root / "linkdir")
    assert build_allowlist(root) == {"ok.txt": b"ok"}


def test_a_missing_directory_gives_an_empty_allowlist(tmp_path: Path) -> None:
    assert build_allowlist(tmp_path / "nope") == {}


def _key(tmp_path):
    key = tmp_path / "keys.env"
    key.write_text("K=1")
    return key


def test_same_file_hard_link_and_symlink_are_the_key_file(tmp_path):
    key = _key(tmp_path)
    link = tmp_path / "hard"
    os.link(key, link)
    sym = tmp_path / "sym"
    sym.symlink_to(key)
    assert is_key_file(key, key)
    assert is_key_file(link, key)
    assert is_key_file(sym, key)


def test_other_file_missing_key_and_none_are_false(tmp_path):
    key = _key(tmp_path)
    other = tmp_path / "other"
    other.write_text("x")
    assert not is_key_file(other, key)
    assert not is_key_file(other, tmp_path / "absent.env")
    assert not is_key_file(other, None)
    assert not is_key_file(tmp_path / "missing", key)


def test_open_descriptor_compares_device_and_inode_without_samefile(tmp_path, monkeypatch):
    key = _key(tmp_path)
    other = tmp_path / "other"
    other.write_text("x")
    module = sys.modules["scenevoice.web.is_key_file"]
    calls: list[str] = []

    def boom(*a, **k):
        calls.append("samefile")
        raise AssertionError("samefile must not be used with a descriptor")

    monkeypatch.setattr(module.os.path, "samefile", boom)
    fd_key = os.open(key, os.O_RDONLY)
    fd_other = os.open(other, os.O_RDONLY)
    try:
        assert is_key_file(other, key, fd=fd_key)  # the descriptor decides, not the path
        assert not is_key_file(key, key, fd=fd_other)
        assert not is_key_file(key, None, fd=fd_key)
        assert not is_key_file(key, tmp_path / "absent.env", fd=fd_key)
    finally:
        os.close(fd_key)
        os.close(fd_other)
    assert calls == []
    try:
        module.os.path.samefile(key, key)  # positive control: the patch is live
    except AssertionError:
        pass
    assert calls == ["samefile"]


@pytest.mark.parametrize(
    "key_file",
    ["/w/ws/keys.env", "/w/ws/p/script.md", "/w/ws/p/../keys.env", "/w/WS/KEYS.env", "/w/ws/", "/w/ws", "/w/ws/./a/../b"],
)
def test_equal_inside_or_differently_spelled_inside_overlaps(key_file):
    assert key_file_overlap("/w/ws", key_file)


@pytest.mark.parametrize("key_file", ["/w/ws-other/keys.env", "/w/keys.env", "/elsewhere/keys.env", "/w/ws/../ws2/keys.env"])
def test_sibling_parent_and_unrelated_do_not_overlap(key_file):
    assert not key_file_overlap("/w/ws", key_file)


def test_root_workspace_contains_everything():
    assert key_file_overlap("/", "/anything/keys.env")


def test_makes_no_filesystem_call(monkeypatch):
    calls: list[str] = []
    module = sys.modules["scenevoice.web.key_file_overlap"]
    monkeypatch.setattr(module.os.path, "realpath", lambda p, **k: calls.append("realpath") or p)
    monkeypatch.setattr(module.os, "lstat", lambda p, **k: calls.append("lstat") or None)
    monkeypatch.setattr(module.os.path, "exists", lambda p: calls.append("exists") or True)
    assert key_file_overlap("/w/ws", "/w/ws/keys.env")
    assert calls == []
    module.os.path.exists("/")  # positive control
    assert calls == ["exists"]


def test_relative_override_becomes_absolute_against_server_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = {"SCENEVOICE_KEYS_FILE": "rel/keys.env", "HOME": "/h"}
    assert absolute_keys_file(env) == {
        "SCENEVOICE_KEYS_FILE": str(tmp_path.resolve() / "rel" / "keys.env"),
        "HOME": "/h",
    }
    assert env["SCENEVOICE_KEYS_FILE"] == "rel/keys.env"


@pytest.mark.parametrize("env", [{"HOME": "/h"}, {"SCENEVOICE_KEYS_FILE": "/abs/keys.env"}])
def test_absolute_or_unset_passes_through(env):
    assert absolute_keys_file(env) == env


@pytest.mark.parametrize("blank", ["", " ", "\t \n"])
def test_blank_counts_as_unset_and_is_untouched(blank):
    assert absolute_keys_file({"SCENEVOICE_KEYS_FILE": blank}) == {"SCENEVOICE_KEYS_FILE": blank}


def test_exact_entry_is_true_only_for_the_listed_spelling(tmp_path):
    (tmp_path / "script.md").write_text("x")
    assert exact_entry(tmp_path, "script.md")
    assert not exact_entry(tmp_path, "other.md")
    assert not exact_entry(tmp_path / "missing", "script.md")


def test_exact_entry_refuses_a_differently_cased_lookup_against_the_listing(fake_listing, tmp_path):
    asked = fake_listing("exact_entry", ["My-Video"])
    assert not exact_entry(tmp_path, "my-video")
    assert exact_entry(tmp_path, "My-Video")
    assert asked == [str(tmp_path)] * 2  # positive control: the fake was used


def test_spelling_conflict_true_only_for_an_unlisted_casefold_twin(fake_listing, tmp_path):
    fake_listing("spelling_conflict", ["Script.md", "audio"])
    assert spelling_conflict(tmp_path, "script.md")
    assert not spelling_conflict(tmp_path, "Script.md")  # listed exactly
    assert not spelling_conflict(tmp_path, "notes.md")  # nothing similar


def test_spelling_conflict_is_false_for_a_missing_directory(tmp_path):
    assert not spelling_conflict(tmp_path / "missing", "script.md")
