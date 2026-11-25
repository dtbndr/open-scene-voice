import json
import os
import sys
from pathlib import Path

import pytest
from web_http_helper import make_request

from scenevoice.web import (
    get_script,
    is_project_id,
    list_projects,
    make_project,
    project_dir,
)


def test_a_missing_root_is_an_empty_list_and_nothing_is_created(tmp_path):
    root = tmp_path / "ws"
    assert list_projects(root) == []
    assert not root.exists()


def test_only_real_directories_matching_the_id_rule_are_listed(tmp_path):
    for name in ("alpha", "beta", ".hidden", "Caps", "has space"):
        (tmp_path / name).mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "alpha")
    (tmp_path / "afile").write_text("x")
    assert sorted(entry["id"] for entry in list_projects(tmp_path)) == ["alpha", "beta"]


def test_every_listed_id_resolves_through_project_dir(tmp_path):
    for name in ("alpha", "beta", "Caps"):
        (tmp_path / name).mkdir()
    listed = list_projects(tmp_path)
    assert listed
    assert all(project_dir(tmp_path, entry["id"]) is not None for entry in listed)


def test_a_capitalised_folder_is_neither_listed_nor_resolvable_by_its_lowercase_spelling(tmp_path, fake_listing):
    (tmp_path / "my-video").mkdir()  # stands in for the case-insensitive volume answering the lowercase lstat
    asked = fake_listing("list_projects", ["My-Video"])
    assert list_projects(tmp_path) == []
    assert asked
    assert project_dir(tmp_path, "my-video") is None


def test_modified_is_the_script_time_else_the_folder_time_newest_first_then_by_id(tmp_path):
    def project(name, script_time=None, folder_time=None):
        directory = tmp_path / name
        directory.mkdir()
        if script_time is not None:
            (directory / "script.md").write_text("x")
            os.utime(directory / "script.md", (script_time, script_time))
        if folder_time is not None:
            os.utime(directory, (folder_time, folder_time))

    project("old", script_time=100, folder_time=900)  # the folder time is ignored when a script exists
    project("empty", folder_time=300)
    project("tie-b", script_time=300, folder_time=1)
    project("tie-a", script_time=300, folder_time=1)
    assert list_projects(tmp_path) == [
        {"id": "empty", "modified": 300},
        {"id": "tie-a", "modified": 300},
        {"id": "tie-b", "modified": 300},
        {"id": "old", "modified": 100},
    ]


def test_a_script_that_is_a_symlink_or_a_folder_falls_back_to_the_folder_time(tmp_path):
    (tmp_path / "linked").mkdir()
    (tmp_path / "elsewhere.md").write_text("x")
    os.utime(tmp_path / "elsewhere.md", (5, 5))
    (tmp_path / "linked" / "script.md").symlink_to(tmp_path / "elsewhere.md")
    (tmp_path / "dirscript").mkdir()
    (tmp_path / "dirscript" / "script.md").mkdir()
    os.utime(tmp_path / "linked", (700, 700))
    os.utime(tmp_path / "dirscript", (800, 800))
    assert list_projects(tmp_path) == [{"id": "dirscript", "modified": 800}, {"id": "linked", "modified": 700}]


def test_creates_the_root_lazily_and_the_folder(tmp_path):
    root = tmp_path / "deep" / "ws"
    assert make_project(root, "My Video!") == "my-video"
    assert (root / "my-video").is_dir()
    assert os.listdir(root) == ["my-video"]


def test_a_taken_slug_gets_the_next_number(tmp_path):
    assert [make_project(tmp_path, "My Video") for _ in range(3)] == ["my-video", "my-video-2", "my-video-3"]


def test_a_stale_listing_loses_the_race_on_mkdir_and_moves_on(tmp_path, fake_listing):
    (tmp_path / "my-video").mkdir()
    (tmp_path / "my-video-2").mkdir()
    asked = fake_listing("make_project", [])
    assert make_project(tmp_path, "my video") == "my-video-3"
    assert asked  # positive control: the listing fake was the one consulted


def test_a_symlink_named_like_the_slug_is_taken(tmp_path):
    (tmp_path / "my-video").symlink_to(tmp_path / "nowhere")
    assert make_project(tmp_path, "my video") == "my-video-2"


def test_a_differently_cased_folder_makes_the_slug_taken(tmp_path, fake_listing):
    asked = fake_listing("make_project", ["My-Video"])
    assert make_project(tmp_path, "my video") == "my-video-2"
    assert asked


@pytest.mark.parametrize("name", ["a" * 100, "a" * 61 + " b", "###", "Ünïcode name"])
def test_every_id_satisfies_the_id_rule_even_with_a_suffix(tmp_path, name):
    ids = [make_project(tmp_path, name) for _ in range(12)]
    assert len(set(ids)) == 12
    assert all(is_project_id(value) and len(value) <= 64 for value in ids)
    assert all((tmp_path / value).is_dir() for value in ids)


def test_a_long_name_keeps_room_for_the_suffix(tmp_path):
    first = make_project(tmp_path, "a" * 100)
    second = make_project(tmp_path, "a" * 100)
    assert (first, second) == ("a" * 64, "a" * 62 + "-2")


def test_the_cut_never_leaves_a_dash_before_the_suffix(tmp_path):
    make_project(tmp_path, "a" * 61 + " b")
    assert make_project(tmp_path, "a" * 61 + " b") == "a" * 61 + "-2"


def test_the_root_may_be_given_as_a_path_object(tmp_path):
    assert isinstance(tmp_path, Path)
    assert make_project(tmp_path / "x", "n") == "n"


def test_existing_directory_returns_its_path(tmp_path):
    (tmp_path / "my-video").mkdir()
    assert project_dir(tmp_path, "my-video") == tmp_path / "my-video"


def test_invalid_id_returns_none_before_any_lstat(tmp_path, monkeypatch):
    calls: list[str] = []
    module = sys.modules["scenevoice.web.project_dir"]
    monkeypatch.setattr(module.os, "lstat", lambda p, **k: calls.append("lstat") or None)
    assert project_dir(tmp_path, "../x") is None
    assert project_dir(tmp_path, "My-Video") is None
    assert calls == []
    module.os.lstat(tmp_path)  # positive control
    assert calls == ["lstat"]


def test_inexact_spelling_returns_none_before_lstat(tmp_path, fake_listing, monkeypatch):
    asked = fake_listing("project_dir", ["My-Video"])
    calls: list[str] = []
    module = sys.modules["scenevoice.web.project_dir"]
    monkeypatch.setattr(module.os, "lstat", lambda p, **k: calls.append("lstat") or None)
    assert project_dir(tmp_path, "my-video") is None
    assert asked  # positive control: the fake listing was consulted
    assert calls == []


def test_missing_file_symlink_and_dot_directory_return_none(tmp_path):
    (tmp_path / "plain").write_text("x")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "link").symlink_to(elsewhere)
    (tmp_path / ".hidden").mkdir()
    assert project_dir(tmp_path, "absent") is None
    assert project_dir(tmp_path, "plain") is None
    assert project_dir(tmp_path, "link") is None
    assert project_dir(tmp_path, ".hidden") is None


def test_symlinked_root_is_fine_when_the_caller_resolved_it(tmp_path):
    real = tmp_path / "real"
    (real / "p").mkdir(parents=True)
    link = tmp_path / "rootlink"
    link.symlink_to(real)
    assert project_dir(link.resolve(), "p") == real.resolve() / "p"


@pytest.fixture
def project(tmp_path):
    directory = tmp_path.resolve() / "ws" / "p"
    directory.mkdir(parents=True)
    return directory


def ask(project, key_file=None, project_id="p"):
    handler = get_script(lambda: project.parent, project_id, key_file)
    response = handler(make_request("GET", f"/api/projects/{project_id}/script"))
    return response, json.loads(response.body)


def assert_plain_refusal(response, body, *secrets):
    assert (response.status, body["error"]["kind"]) == (400, "bad_request")
    text = body["error"]["message"]
    assert text and "/" not in text and "script.md" not in text
    for secret in secrets:
        assert str(secret) not in response.body.decode()


def test_an_absent_script_is_an_empty_text(project):
    response, body = ask(project)
    assert (response.status, response.no_store, body) == (200, True, {"text": ""})


@pytest.mark.parametrize(
    "text",
    ["plain", "a\r\nb\r\n", "é ✓ 😀"],
)
def test_a_present_script_comes_back_exactly(project, text):
    (project / "script.md").write_bytes(text.encode("utf-8"))
    response, body = ask(project)
    assert (response.status, body) == (200, {"text": text})


def test_a_missing_project_is_a_404_not_found(project):
    response, body = ask(project, project_id="other")
    assert (response.status, body["error"]["kind"]) == (404, "not_found")


# Read outside the project: a symlinked script.md is refused.
def test_a_symlink_named_script_md_is_a_plain_400(project, tmp_path):
    (tmp_path / "elsewhere.txt").write_text("secret words")
    (project / "script.md").symlink_to(tmp_path / "elsewhere.txt")
    response, body = ask(project)
    assert_plain_refusal(response, body, tmp_path, "secret words")


def test_the_key_file_as_script_md_is_a_plain_400_with_no_key_byte(project):
    (project / "script.md").write_text("GOOGLE_KEY=hunter2-key-bytes")
    response, body = ask(project, key_file=project / "script.md")
    assert_plain_refusal(response, body, "hunter2")


def test_a_hard_link_to_the_key_file_is_a_plain_400_with_no_key_byte(project, tmp_path):
    key_file = tmp_path / "keys.env"
    key_file.write_text("GOOGLE_KEY=hunter2-key-bytes")
    os.link(key_file, project / "script.md")
    response, body = ask(project, key_file=key_file)
    assert_plain_refusal(response, body, "hunter2")


@pytest.mark.parametrize("with_key_file", [False])
def test_a_script_hard_linked_to_another_file_is_a_plain_400_never_an_empty_editor(project, tmp_path, with_key_file):
    other = tmp_path / "other.txt"
    other.write_text("linked words")
    os.link(other, project / "script.md")
    key_file = tmp_path / "keys.env" if with_key_file else None
    response, body = ask(project, key_file=key_file)
    assert_plain_refusal(response, body, "linked words")
