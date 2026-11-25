import json

from job_events_helper import finished_hub, scene_event, status_of

from scenevoice.web import MESSAGE_LIMIT, JobEvents, JobStatus, current_job_json


def line(**fields: object) -> str:
    return json.dumps(fields)


def test_events_are_numbered_from_one_and_the_job_ends_with_end() -> None:
    hub = finished_hub(2)
    read = hub.read(1, 0, 0.0)
    assert [event["seq"] for event in read.events] == [1, 2, 3]
    assert [event["type"] for event in read.events] == ["scene", "scene", "end"]
    assert read.ended is True
    assert hub.latest().number == 1
    assert hub.latest().end_seq == 3


def test_the_end_event_is_the_final_state_with_the_failure_worked_out_from_the_events() -> None:
    hub = JobEvents()
    hub.add({"type": "fail", "kind": "quota", "message": "m", "scene": 2, "line": None, "status": 429})
    status = status_of("failed", failure="SceneVoice stopped with an error before the job was finished.")
    hub.finish(status)
    end = hub.read(1, 0, 0.0).events[-1]
    assert end == {"seq": 2, "type": "end", **current_job_json(status, hub.latest_events())}
    assert end["job"]["failure"]["kind"] == "quota"  # type: ignore[index]


def test_a_job_with_no_output_still_has_a_number_and_an_end() -> None:
    hub = JobEvents()
    hub.finish(JobStatus(state="done", kind="pack", project="p", mode="all"))
    assert [event["type"] for event in hub.read(1, 0, 0.0).events] == ["end"]


def test_the_next_job_gets_the_next_number_and_a_fresh_seq() -> None:
    hub = finished_hub(1)
    hub.add(scene_event(1))
    assert hub.latest().number == 2
    assert hub.latest().live is True
    assert [event["seq"] for event in hub.read(2, 0, 0.0).events] == [1]
    assert [event["type"] for event in hub.read(1, 0, 0.0).events] == []  # job 1 is gone, never mixed into job 2


def test_a_read_after_the_last_seq_is_empty_and_a_read_gives_only_what_is_newer() -> None:
    hub = JobEvents()
    hub.add(scene_event(1))
    hub.add(scene_event(2))
    assert [event["seq"] for event in hub.read(1, 1, 0.0).events] == [2]
    read = hub.read(1, 2, 0.0)
    assert (read.events, read.ended, read.closed) == ((), False, False)


def test_the_observer_scrubs_parses_and_counts_each_finished_scene() -> None:
    hub = JobEvents()
    counted: list[int] = []
    observer = hub.observer(scrub=lambda text: text.replace("/secret", "X"), on_scene_done=lambda: counted.append(1))
    observer.line(line(command="synth", event="scene", message="a /secret", state="started", scene=1, total=2))
    observer.line(line(command="synth", event="scene", message="b", state="done", scene=1, total=2))
    observer.line(line(command="synth", event="note", message="n /secret"))
    observer.line(line(command="synth", event="scene", message="c", state="done", scene=2, total=2))
    observer.line("Traceback (most recent call last):")
    observer.line(line(command="synth", event="bogus", message="x"))
    observer.flush()
    observer.end(status_of("done", scenes_done=2))
    events = hub.read(1, 0, 0.0).events
    assert [(event["type"], event["message"]) for event in events[:4]] == [
        ("scene", "a X"),
        ("scene", "b"),
        ("note", "n X"),
        ("scene", "c"),
    ]
    assert [event["type"] for event in events] == ["scene", "scene", "note", "scene", "end"]
    assert len(counted) == 2


def boom(*args: object) -> str:
    raise RuntimeError("boom")


def test_a_scrub_that_fails_drops_the_event_rather_than_forwarding_it_unscrubbed() -> None:
    hub = JobEvents()
    observer = hub.observer(scrub=boom, on_scene_done=lambda: None)
    observer.line(line(command="synth", event="note", message="/secret/path"))
    assert hub.latest().number == 0


def test_a_message_is_scrubbed_whole_and_only_then_cut_so_a_path_across_the_cut_cannot_leak() -> None:
    secret = "/Users/someone/secret-project"
    padding = "x" * (MESSAGE_LIMIT - 10)
    hub = JobEvents()
    observer = hub.observer(scrub=lambda text: text.replace(secret, ""), on_scene_done=lambda: None)
    observer.line(line(command="synth", event="note", message=padding + secret + " tail"))
    message = hub.read(1, 0, 0.0).events[0]["message"]
    assert "/Users" not in str(message) and "secret" not in str(message)
    assert message == (padding + " tail")[:MESSAGE_LIMIT]
