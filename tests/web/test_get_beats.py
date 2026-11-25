import json

import pytest
from project_routes_helper import make_project_routes
from web_http_helper import make_request

from scenevoice.web import get_beats

SHA = "a" * 64
DOCUMENT = {"version": 1, "script_sha256": SHA, "scenes": [{"n": 1, "beats": ["é ✓"]}]}


@pytest.fixture
def project(tmp_path):
    directory = tmp_path.resolve() / "ws" / "p"
    directory.mkdir(parents=True)
    return directory


def ask(project, key_file=None, project_id="p"):
    handler = get_beats(lambda: project.parent, project_id, key_file)
    response = handler(make_request("GET", f"/api/projects/{project_id}/beats"))
    return response, json.loads(response.body)


def assert_plain_refusal(response, body, secret):
    assert (response.status, body["error"]["kind"]) == (400, "bad_request")
    text = body["error"]["message"]
    assert text and "/" not in text and "beats.json" not in text
    assert secret not in response.body.decode()


def test_a_light_valid_document_is_served_unchanged(project):
    (project / "beats.json").write_text(json.dumps(DOCUMENT, ensure_ascii=False), encoding="utf-8")
    response, body = ask(project)
    assert (response.status, response.no_store, body) == (200, True, DOCUMENT)


def test_an_absent_file_is_a_404_with_the_no_beats_words(project):
    response, body = ask(project)
    assert (response.status, body["error"]["kind"], body["error"]["message"]) == (404, "not_found", "There are no beats yet.")


def test_a_document_failing_the_light_check_is_a_plain_400_and_not_served(project):
    (project / "beats.json").write_text(json.dumps({**DOCUMENT, "version": 2, "scenes": ["SECRET-SCENE"]}))
    assert_plain_refusal(*ask(project), "SECRET-SCENE")


def ask_through_routes(project, key_file):
    table = make_project_routes(root_getter=lambda: project.parent, key_file=key_file)
    response = table["/api/projects/p/beats"]["GET"](make_request("GET", "/api/projects/p/beats"))
    return response, json.loads(response.body)


# Key leak: a beats.json that is the closure's key file is never served, even when its bytes pass the light check;
# asked through the route table so the route must hand its key file to the reader.
def test_a_beats_json_that_is_the_key_file_is_a_plain_400_and_not_served(project):
    (project / "beats.json").write_text(json.dumps({**DOCUMENT, "scenes": ["GOOGLE_KEY=leak-me"]}))
    assert_plain_refusal(*ask_through_routes(project, project / "beats.json"), "leak-me")


# P1: a 200 body a browser cannot parse (JSON.parse rejects NaN) must be the plain 400 instead.
def test_a_light_valid_document_holding_nan_is_a_plain_400(project):
    (project / "beats.json").write_text(
        '{"version": 1, "script_sha256": "' + SHA + '", "scenes": [{"n": NaN}]}'
    )
    response, body = ask(project)
    assert (response.status, body["error"]["kind"]) == (400, "bad_request")
