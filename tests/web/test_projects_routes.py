import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from project_routes_helper import make_project_routes
from web_http_helper import make_request

from scenevoice.web import make_root_getter

KEY_MESSAGE = "The workspace folder holds your key file. Choose another folder."


def routes_for(getter, **options):
    return make_project_routes(root_getter=getter, **options)


def call(routes, method, body=None):
    request = replace(make_request(method, "/api/projects"), json_body=body)
    return routes["/api/projects"][method](request)


@pytest.fixture
def root(tmp_path):
    return tmp_path.resolve() / "ws"


def test_get_lists_the_projects_with_the_resolved_root(root):
    (root / "alpha").mkdir(parents=True)
    response = call(routes_for(lambda: root), "GET")
    assert (response.status, response.no_store) == (200, True)
    assert ("Content-Type", "application/json; charset=utf-8") in response.headers
    body = json.loads(response.body)
    assert body["workspace"] == str(root)
    assert [entry["id"] for entry in body["projects"]] == ["alpha"]


def test_get_on_a_missing_root_is_empty_and_creates_nothing(root):
    assert json.loads(call(routes_for(lambda: root), "GET").body)["projects"] == []
    assert not root.exists()


def test_post_creates_only_the_folder_and_answers_201(root):
    response = call(routes_for(lambda: root), "POST", {"name": "  My Video "})
    assert (response.status, json.loads(response.body)) == (201, {"id": "my-video"})
    assert os.listdir(root) == ["my-video"]
    assert os.listdir(root / "my-video") == []


@pytest.mark.parametrize("body", [[], {"name": 5}, {"name": "   "}])
def test_post_refuses_a_bad_body_in_plain_words_and_creates_nothing(root, body):
    response = call(routes_for(lambda: root), "POST", body)
    assert response.status == 400
    assert json.loads(response.body)["error"]["kind"] == "bad_request"
    assert not root.exists()


def key_workspace(tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    key_file = keys / "keys.env"
    key_file.write_text("SECRETMARKER")
    workspace = tmp_path / "ws"
    workspace.symlink_to(keys)
    return workspace, key_file, keys


def test_a_workspace_symlinked_onto_the_key_file_folder_fails_closed_for_both_routes(tmp_path):
    workspace, key_file, keys = key_workspace(tmp_path)
    routes = routes_for(make_root_getter(workspace, key_file), key_file=key_file)
    for method, body in (("GET", None), ("POST", {"name": "x"})):
        response = call(routes, method, body)
        assert response.status == 400
        assert json.loads(response.body) == {"error": {"kind": "bad_request", "message": KEY_MESSAGE}}
        assert os.listdir(keys) == ["keys.env"]
        assert b"SECRETMARKER" not in response.body


DOCUMENTS_MESSAGE = (
    "SceneVoice could not open your Documents folder. Open System Settings, Privacy and Security, "
    "Files and Folders, and allow Terminal, then try again."
)


@pytest.mark.parametrize(
    ("method", "body", "module"),
    [("GET", None, "list_projects"), ("POST", {"name": "x"}, "make_project")],
)
def test_denied_documents_folder_is_a_plain_message_for_both_project_routes(root, monkeypatch, method, body, module):
    # P1: a denied macOS Documents prompt must not break the first run with "Something went wrong."
    # The PermissionError is raised inside the listing itself (not by root_getter), so a catch placed
    # around root_getter alone fails this test.
    root.mkdir(parents=True)
    real = os.listdir
    calls = []

    def denied(path="."):
        if Path(path) == root:
            calls.append(path)
            raise PermissionError(1, "Operation not permitted")
        return real(path)

    monkeypatch.setattr(sys.modules[f"scenevoice.web.{module}"].os, "listdir", denied)
    response = call(routes_for(lambda: root), method, body)
    assert calls
    assert response.status == 500
    assert json.loads(response.body) == {"error": {"kind": "internal_error", "message": DOCUMENTS_MESSAGE}}
