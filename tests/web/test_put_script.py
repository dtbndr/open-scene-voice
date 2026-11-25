import json
import os
import sys
import threading
from dataclasses import replace

import pytest
from web_http_helper import make_request

from scenevoice.web import JobRunner, put_script


@pytest.fixture
def project(tmp_path):
    directory = tmp_path.resolve() / "ws" / "p"
    directory.mkdir(parents=True)
    return directory


def save(project, body, key_file=None, project_id="p"):
    handler = put_script(lambda: project.parent, project_id, key_file, JobRunner(cwd=project.parent, env={}), threading.Lock())
    request = replace(make_request("PUT", f"/api/projects/{project_id}/script"), json_body=body)
    response = handler(request)
    return response, json.loads(response.body)


def assert_plain_refusal(response, body):
    assert (response.status, body["error"]["kind"]) == (400, "bad_request")
    text = body["error"]["message"]
    assert text and "/" not in text


def test_a_save_answers_200_saved_true(project):
    response, body = save(project, {"text": "hello"})
    assert (response.status, response.no_store, body) == (200, True, {"saved": True})


@pytest.mark.parametrize(
    "text", ["plain", "a\r\nb\r\n", "é ✓ 😀", ""]
)
def test_the_bytes_on_disk_are_the_utf8_of_the_text_exactly(project, text):
    assert save(project, {"text": text})[0].status == 200
    assert (project / "script.md").read_bytes() == text.encode("utf-8")


def test_an_existing_script_is_replaced_and_no_temp_file_stays(project):
    (project / "script.md").write_text("old")
    save(project, {"text": "new"})
    assert (project / "script.md").read_text() == "new"
    assert os.listdir(project) == ["script.md"]


def test_a_failed_write_keeps_the_old_script_and_leaves_no_temp_file(project, monkeypatch):
    (project / "script.md").write_text("old")

    def boom(src, dst):
        raise OSError("disk went away")

    monkeypatch.setattr(sys.modules["scenevoice.web.write_file_atomic"].os, "replace", boom)
    with pytest.raises(OSError):
        save(project, {"text": "new"})
    assert (project / "script.md").read_text() == "old"
    assert os.listdir(project) == ["script.md"]


def test_a_missing_project_is_a_404_and_nothing_is_created(project):
    response, body = save(project, {"text": "x"}, project_id="other")
    assert (response.status, body["error"]["kind"]) == (404, "not_found")
    assert os.listdir(project.parent) == ["p"]
    assert os.listdir(project) == []


@pytest.mark.parametrize("body", [[], {"text": 5}, {}])
def test_a_body_without_a_string_text_is_a_400_and_writes_nothing(project, body):
    assert_plain_refusal(*save(project, body))
    assert os.listdir(project) == []


# Write outside the project / key leak: the key file is never overwritten through script.md.
def test_a_script_md_that_is_the_key_file_is_a_plain_400_and_stays_untouched(project):
    (project / "script.md").write_text("GOOGLE_KEY=keep-me")
    assert_plain_refusal(*save(project, {"text": "x"}, key_file=project / "script.md"))
    assert (project / "script.md").read_text() == "GOOGLE_KEY=keep-me"
    assert os.listdir(project) == ["script.md"]


def test_a_script_md_with_a_second_hard_link_is_a_plain_400_and_the_linked_bytes_stay(project, tmp_path):
    other = tmp_path / "other.txt"
    other.write_text("linked words")
    os.link(other, project / "script.md")
    assert_plain_refusal(*save(project, {"text": "x"}))
    assert other.read_text() == "linked words"
    assert os.listdir(project) == ["script.md"]


def test_a_real_differently_cased_file_is_a_plain_400_on_any_volume(project):
    (project / "Script.md").write_text("theirs")
    assert_plain_refusal(*save(project, {"text": "x"}))
    assert os.listdir(project) == ["Script.md"]
    assert (project / "Script.md").read_text() == "theirs"


# Busy gate (J2): the handler takes the script lock around its busy check and its write.
def saver(project, runner, lock, project_id="p"):
    handler = put_script(lambda: project.parent, project_id, None, runner, lock)
    request = replace(make_request("PUT", f"/api/projects/{project_id}/script"), json_body={"text": "new"})
    return lambda: handler(request)


@pytest.mark.parametrize(
    ("kind_", "message"),
    [("synth", "SceneVoice is busy voicing.")],
)
def test_a_save_while_the_slot_is_held_is_409_busy_with_the_running_kinds_message_and_writes_nothing(project, kind_, message):
    runner = JobRunner(cwd=project.parent, env={})
    assert runner.reserve(kind_, "other") is not None  # a `starting` slot refuses too, and in every project
    (project / "script.md").write_text("old")
    response = saver(project, runner, threading.Lock())()
    body = json.loads(response.body)
    assert (response.status, body["error"]["kind"], body["error"]["message"]) == (409, "busy", message)
    assert (project / "script.md").read_text() == "old"
    assert os.listdir(project) == ["script.md"]


def test_only_a_differently_spelled_script_is_a_plain_400_and_nothing_is_written(project, monkeypatch):
    real = os.listdir

    def listing(directory="."):
        return ["Script.md"] if os.fspath(directory) == str(project) else real(directory)

    monkeypatch.setattr(os, "listdir", listing)
    assert os.listdir(project) == ["Script.md"]  # positive control: the patch is live
    assert_plain_refusal(*save(project, {"text": "x"}))
    assert real(project) == []
