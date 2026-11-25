import json
import os
import sys
from dataclasses import replace

import pytest
from project_routes_helper import make_project_routes
from web_http_helper import make_request

from scenevoice.web import chain_routes, serve_audio

PAYLOAD = bytes(range(256)) * 4  # 1024 distinguishable bytes
SIZE = len(PAYLOAD)


@pytest.fixture
def project(tmp_path):
    directory = tmp_path.resolve() / "ws" / "p"
    (directory / "audio").mkdir(parents=True)
    (directory / "audio" / "001.wav").write_bytes(PAYLOAD)
    return directory


def ask(project, file="001.wav", range_header=None, key_file=None, project_id="p"):
    headers = [("host", "127.0.0.1:5000")]
    if range_header is not None:
        headers.append(("range", range_header))
    handler = serve_audio(lambda: project.parent, project_id, file, key_file)
    return handler(make_request("GET", f"/api/projects/{project_id}/audio/{file}", headers))


def kind(response):
    return (response.status, json.loads(response.body)["error"]["kind"])


def test_a_plain_request_is_a_200_with_the_whole_file_and_the_audio_headers(project):
    response = ask(project)
    assert (response.status, response.body) == (200, PAYLOAD)
    assert response.headers == (("Content-Type", "audio/wav"), ("Accept-Ranges", "bytes"))
    assert response.no_store is True


@pytest.mark.parametrize(
    ("header", "start", "end"),
    [("bytes=0-99", 0, 99), ("bytes=-50", SIZE - 50, SIZE - 1)],
)
def test_one_range_is_a_206_with_exactly_that_slice_and_content_range(project, header, start, end):
    response = ask(project, range_header=header)
    assert (response.status, response.body) == (206, PAYLOAD[start : end + 1])
    assert dict(response.headers) == {
        "Content-Type": "audio/wav",
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{SIZE}",
    }
    assert response.no_store is True


@pytest.mark.parametrize("header", ["bytes=1024-"])
def test_an_unsatisfiable_range_is_a_416_naming_the_size(project, header):
    response = ask(project, range_header=header)
    assert kind(response) == (416, "bad_request")
    assert dict(response.headers)["Content-Range"] == f"bytes */{SIZE}"


@pytest.mark.parametrize("header", ["bytes=0-1,5-6"])
def test_an_ignored_range_is_a_200_with_the_whole_file(project, header):
    response = ask(project, range_header=header)
    assert (response.status, response.body) == (200, PAYLOAD)
    assert "Content-Range" not in dict(response.headers)


@pytest.mark.parametrize("file", ["01.wav", "../001.wav"])
# Read outside the project: a name that is not audio NNN.wav never reaches the filesystem.
def test_a_name_failing_the_allowlist_is_a_404_without_touching_the_filesystem(project, monkeypatch, file):
    touched = []
    real = sys.modules["scenevoice.web.exact_entry"].os.listdir

    def spy(path):
        touched.append(path)
        return real(path)

    monkeypatch.setattr(sys.modules["scenevoice.web.exact_entry"].os, "listdir", spy)
    assert ask(project, "001.wav").status == 200  # positive control: the spy sees a real read
    assert touched
    touched.clear()
    assert kind(ask(project, file)) == (404, "not_found")
    assert touched == []


def test_a_missing_file_or_a_missing_project_is_a_404_not_found(project):
    assert kind(ask(project, "009.wav")) == (404, "not_found")
    assert kind(ask(project, project_id="other")) == (404, "not_found")
    (project / "script.md").write_text("x")
    (project / "audio" / "003.wav").mkdir()
    assert kind(ask(project, "003.wav")) == (404, "not_found")


def test_a_symlinked_file_and_a_symlinked_audio_directory_are_404(project, tmp_path):
    (tmp_path / "elsewhere.wav").write_bytes(b"secret")
    (project / "audio" / "004.wav").symlink_to(tmp_path / "elsewhere.wav")
    assert kind(ask(project, "004.wav")) == (404, "not_found")
    other = project.parent / "q"
    other.mkdir()
    (other / "audio").symlink_to(project / "audio")
    assert kind(ask(other, project_id="q")) == (404, "not_found")
    assert ask(project).status == 200  # positive control: the target itself is served


# Key leak: the key file and a hard link to it are never served.
def test_a_file_that_is_the_key_file_or_has_a_second_hard_link_is_a_404(project, tmp_path):
    wav = project / "audio" / "001.wav"
    assert ask(project, key_file=tmp_path / "missing.env").status == 200  # positive control
    assert kind(ask(project, key_file=wav)) == (404, "not_found")
    keys = tmp_path / "keys.env"
    keys.write_text("GOOGLE_KEY=hunter2")
    os.link(keys, project / "audio" / "005.wav")
    refused = ask(project, "005.wav", key_file=keys)
    assert kind(refused) == (404, "not_found") and b"hunter2" not in refused.body
    os.link(wav, project / "audio" / "006.wav")
    assert kind(ask(project)) == (404, "not_found")


PROJECT_ID_SAMPLE = "my-video"


def routes():
    return make_project_routes()


def test_the_collection_path_has_get_and_post_handlers():
    table = routes()
    assert set(table["/api/projects"]) == {"GET", "POST"}
    assert "/api/projects" in table
    assert table.get("/api/projects") is not None


@pytest.mark.parametrize(
    "path",
    [
        "/api/projects/..",  # outside the workspace
        "/api/projects/a%2Fb/script",  # outside the workspace
        "//api/projects",
        "/api/projects/A/script",
    ],
)
def test_malformed_or_unbuilt_shapes_are_not_routes(path):
    table = routes()
    assert table.get(path) is None
    assert path not in table
    with pytest.raises(KeyError):
        table[path]


def test_the_detail_path_has_a_get_only_handler_for_a_valid_id():
    table = routes()
    assert set(table["/api/projects/my-video"]) == {"GET"}
    assert "/api/projects/" + "a" * 64 in table
    for path in ("/api/projects/" + "a" * 65, "/api/projects/A", "/api/projects/a/", "/api/projects/a\n", "/api/projects/a%2Fb"):
        assert path not in table


def test_the_jobs_path_has_a_post_only_handler_for_a_valid_id_and_no_other_shape():
    table = routes()
    assert set(table["/api/projects/my-video/jobs"]) == {"POST"}


def test_chain_checks_the_keys_dict_first_then_the_project_routes():
    keys_get, keys_clash = object(), object()
    keys = {"/api/keys": {"GET": keys_get}, "/api/projects": {"GET": keys_clash}}
    chained = chain_routes(keys, routes())
    assert chained["/api/keys"]["GET"] is keys_get
    assert chained["/api/projects"]["GET"] is keys_clash  # keys first: the two path spaces never overlap in practice
    assert set(chain_routes({"/api/keys": {}}, routes())["/api/projects"]) == {"GET", "POST"}


def test_the_script_path_has_get_and_put_handlers_with_the_id_bound_in():
    table = routes()
    assert set(table["/api/projects/my-video/script"]) == {"GET", "PUT"}
    assert "/api/projects/my-video/script" in table
    assert set(table["/api/projects/a/script"]) == {"GET", "PUT"}
    assert "/api/projects/" + "a" * 64 + "/script" in table
    assert "/api/projects/" + "a" * 65 + "/script" not in table


def test_the_script_handlers_receive_the_closure_key_file_and_refuse_the_key_file_and_a_second_link(tmp_path):
    root = tmp_path.resolve() / "ws"
    (root / "p").mkdir(parents=True)
    keys = tmp_path / "keys.env"
    keys.write_text("GOOGLE_KEY=hunter2")

    def answers(key_file):
        table = make_project_routes(root_getter=lambda: root, key_file=key_file)
        methods = table["/api/projects/p/script"]
        put = replace(make_request("PUT", "/api/projects/p/script"), json_body={"text": "x"})
        return [
            methods["GET"](make_request("GET", "/api/projects/p/script")),
            methods["PUT"](put),
        ]

    os.link(keys, root / "p" / "script.md")  # a second hard link: refused whatever the closure holds
    for response in answers(None):
        assert (response.status, json.loads(response.body)["error"]["kind"]) == (400, "bad_request")
    os.unlink(root / "p" / "script.md")
    (root / "p" / "script.md").write_text("GOOGLE_KEY=hunter2")  # nlink 1: only the closure key file can refuse it
    assert [r.status for r in answers(None)] == [200, 200]
    (root / "p" / "script.md").write_text("GOOGLE_KEY=hunter2")
    for response in answers(root / "p" / "script.md"):
        assert (response.status, json.loads(response.body)["error"]["kind"]) == (400, "bad_request")
        assert b"hunter2" not in response.body


def test_the_audio_path_has_a_get_handler_with_the_id_and_file_bound_in():
    table = routes()
    assert set(table["/api/projects/my-video/audio/001.wav"]) == {"GET"}
    assert "/api/projects/" + "a" * 64 + "/audio/001.wav" in table
    assert "/api/projects/" + "a" * 65 + "/audio/001.wav" not in table


def test_the_audio_handler_receives_the_closure_key_file_so_a_hard_link_to_it_answers_404(tmp_path):
    root = tmp_path.resolve() / "ws"
    (root / "p" / "audio").mkdir(parents=True)
    keys = tmp_path / "keys.env"
    keys.write_text("GOOGLE_KEY=hunter2")
    (root / "p" / "audio" / "001.wav").write_text("GOOGLE_KEY=hunter2")  # nlink 1: only the closure key file refuses it
    path = "/api/projects/p/audio/001.wav"

    def answer(key_file):
        table = make_project_routes(root_getter=lambda: root, key_file=key_file)
        return table[path]["GET"](make_request("GET", path))

    assert answer(None).status == 200
    refused = answer(root / "p" / "audio" / "001.wav")
    assert (refused.status, json.loads(refused.body)["error"]["kind"]) == (404, "not_found")
    os.unlink(root / "p" / "audio" / "001.wav")
    os.link(keys, root / "p" / "audio" / "001.wav")  # a second hard link: refused whatever the closure holds
    assert answer(None).status == 404


def test_the_zip_path_has_a_get_handler_that_gets_the_id_and_the_closure_key_file(tmp_path):
    table = routes()
    assert set(table["/api/projects/my-video/pack.zip"]) == {"GET"}
    assert "/api/projects/" + "a" * 65 + "/pack.zip" not in table
    root = tmp_path.resolve() / "ws"
    (root / "p").mkdir(parents=True)
    (root / "p" / "scene_manifest.csv").write_text("GOOGLE_KEY=hunter2")  # nlink 1: only the closure key file refuses it
    path = "/api/projects/p/pack.zip"

    def answer(key_file):
        built = make_project_routes(root_getter=lambda: root, key_file=key_file)
        return built[path]["GET"](make_request("GET", path))

    assert answer(None).status == 200
    refused = answer(root / "p" / "scene_manifest.csv")
    assert (refused.status, json.loads(refused.body)["error"]["kind"]) == (404, "not_found")


def test_the_reveal_path_is_post_only_and_only_for_a_valid_id():
    table = make_project_routes(launch=lambda argv: 0)
    assert set(table["/api/projects/my-video/reveal"]) == {"POST"}
    assert "/api/projects/" + "a" * 65 + "/reveal" not in table
    for path in ("/api/projects/A/reveal", "/api/projects/a/reveal/", "/api/projects/a/reveal/x", "/api/projects/a/reveal.zip"):
        assert path not in table
