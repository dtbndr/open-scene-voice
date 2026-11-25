import json
import threading

import pytest
from job_events_helper import FakeRunner, finished_hub, scene_event, sse_of, status_of

from scenevoice.web import (
    KEEPALIVE_COMMENT,
    JobEvents,
    JobStatus,
    Request,
    StreamResponse,
    current_job_json,
    follow_job,
    format_sse,
    register_job_routes,
)

EVENTS = "/api/jobs/current/events"


def routes(runner: FakeRunner, hub: JobEvents | None = None):
    return register_job_routes(runner, hub or JobEvents(), keepalive=0.0)  # type: ignore[arg-type]


def lei(value: str | None) -> tuple[tuple[str, str], ...]:
    return (("last-event-id", value),) if value is not None else ()


def events_response(runner: FakeRunner, hub: JobEvents, value: str | None = None):
    request = Request("GET", EVENTS, headers=lei(value))
    return routes(runner, hub)[EVENTS]["GET"](request)


def test_the_three_fixed_paths_are_registered_with_their_methods() -> None:
    table = routes(FakeRunner())
    assert {path: sorted(methods) for path, methods in table.items()} == {
        "/api/jobs/current": ["GET"],
        EVENTS: ["GET"],
        "/api/jobs/current/cancel": ["POST"],
    }


def test_the_current_job_route_answers_the_json_and_never_changes_anything() -> None:
    status = status_of("failed", failure="SceneVoice stopped with an error before the job was finished.", notice="Careful.")
    hub = finished_hub(1, state="failed")
    before = hub.read(1, 0, 0.0)
    response = routes(FakeRunner(status), hub)["/api/jobs/current"]["GET"](Request("GET", "/api/jobs/current"))
    assert response.status == 200  # type: ignore[union-attr]
    body = json.loads(response.body)  # type: ignore[union-attr]
    assert body == current_job_json(status, hub.latest_events())
    assert body["job"]["notice"] == "Careful."
    assert body["job"]["failure"]["kind"] == "other"
    assert ("Content-Type", "application/json; charset=utf-8") in response.headers  # type: ignore[union-attr]
    assert response.no_store is True  # type: ignore[union-attr]
    assert hub.read(1, 0, 0.0) == before


def test_the_current_job_route_says_idle_when_nothing_has_run() -> None:
    response = routes(FakeRunner())["/api/jobs/current"]["GET"](Request("GET", "/api/jobs/current"))
    assert json.loads(response.body) == {"state": "idle", "job": None}  # type: ignore[union-attr]


RUN = "a" * 32
CANCEL = "/api/jobs/current/cancel"


def cancel(runner: FakeRunner, body: object):
    return routes(runner)[CANCEL]["POST"](Request("POST", CANCEL, json_body=body))


@pytest.mark.parametrize(
    ("body", "active", "status", "kind"),
    [
        ({}, True, 400, "bad_request"),  # P1 quota: a Cancel with no run id must stop nothing
        ({"run": 7}, True, 400, "bad_request"),
        ({"run": "b" * 32}, True, 409, "changed"),  # P1 quota: a stale id must not stop another project's paid run
        ({"run": RUN}, False, 404, "not_found"),
    ],
)
def test_cancel_refuses_without_a_matching_run_and_stops_nothing(body, active, status, kind) -> None:
    runner = FakeRunner(status_of("running", run=RUN), active=active)
    response = cancel(runner, body)
    assert (response.status, json.loads(response.body)["error"]["kind"]) == (status, kind)  # type: ignore[union-attr]
    assert runner.cancels == 0


def test_cancel_with_the_live_run_stops_it_through_cancel_run_each_time() -> None:
    runner = FakeRunner(status_of("starting", run=RUN), active=True)  # its cancel() fails the test
    for _ in range(2):
        response = cancel(runner, {"run": RUN})
        assert (response.status, json.loads(response.body)) == (200, {"cancelling": True})  # type: ignore[union-attr]
    assert runner.cancels == 2


def test_lookup_by_run_answers_live_then_retained_then_404_and_refuses_a_malformed_id() -> None:
    """P1 quota: a page whose run was replaced can still learn that run's own fate (WS47-02)."""
    live = status_of("running", run=RUN)
    final = status_of("failed", run="c" * 32, failure="x")
    failure = {"kind": "quota", "message": "A's own", "scene": 1, "status": 429}
    runner = FakeRunner(live, active=True)
    runner.retained["c" * 32] = (final, failure)

    def get(query: str):
        return routes(runner)["/api/jobs/current"]["GET"](Request("GET", "/api/jobs/current", query))

    assert json.loads(get(f"run={RUN}").body)["job"]["run"] == RUN  # type: ignore[union-attr]
    retained = json.loads(get("run=" + "c" * 32).body)  # type: ignore[union-attr]
    assert (retained["state"], retained["job"]["failure"]) == ("failed", failure)
    assert get("run=" + "d" * 32).status == 404  # type: ignore[union-attr]
    assert get("run=nope").status == 400  # type: ignore[union-attr]
    assert json.loads(get("").body)["job"]["run"] == RUN  # type: ignore[union-attr]


def ids(response: StreamResponse) -> list[str]:
    return [identifier for identifier, _ in sse_of(response.chunks)]


@pytest.mark.parametrize(
    ("state", "value", "expected"),
    [
        ("idle", None, ["0-1", "0-2"]),
        ("done", None, ["0-1", "1-1", "1-2", "1-3", "1-4"]),
        ("done", "1-2", ["0-1", "1-3", "1-4"]),
        ("done", "1-4", None),  # the end event's own id: 204
        ("done", "7-2", ["0-1", "1-1", "1-2", "1-3", "1-4"]),  # a stale id from another job skips nothing
    ],
)
def test_the_events_route_replays_resumes_or_answers_204(state: str, value: str | None, expected: list[str] | None) -> None:
    hub = finished_hub(3) if state == "done" else JobEvents()
    runner = FakeRunner(status_of(state, scenes_done=3) if state == "done" else JobStatus())
    response = events_response(runner, hub, value)
    assert isinstance(response, StreamResponse)
    if expected is None:
        assert (response.status, response.headers, list(response.chunks)) == (204, (), [])
    elif expected == []:
        assert response.status == 204
    else:
        assert response.status == 200
        assert ids(response) == expected


def test_a_stale_id_from_an_earlier_job_replays_the_whole_current_job() -> None:
    hub = finished_hub(2)
    hub.add(scene_event(1))
    hub.add(scene_event(2))
    hub.finish(status_of("done"))  # now job 2
    response = events_response(FakeRunner(status_of("done")), hub, "1-17")
    assert isinstance(response, StreamResponse)
    assert ids(response) == ["0-1", "2-1", "2-2", "2-3"]


@pytest.mark.parametrize("state", ["starting"])
def test_a_reconnect_while_the_slot_is_held_gets_a_live_stream_never_204(state: str) -> None:
    runner = FakeRunner(status_of(state), active=True)
    response = events_response(runner, JobEvents(), "0-2")
    assert isinstance(response, StreamResponse)
    assert response.status == 200
    first = next(response.chunks)
    assert first.startswith(b"id: 0-1\n")
    response.chunks.close()  # type: ignore[attr-defined]


def take(generator, count: int) -> list[bytes]:
    return [next(generator) for _ in range(count)]


def test_the_snapshot_comes_first_and_is_the_current_job_json_with_an_id_that_has_no_job() -> None:
    status = status_of("running", scenes_done=1)
    runner = FakeRunner(status, active=True)
    hub = JobEvents()
    hub.add(scene_event(1))
    first = sse_of(take(follow_job(runner, hub, 1, 0), 1))
    assert first == [("0-1", {"seq": 1, "type": "state", **current_job_json(status, [])})]


def test_a_finished_job_replays_to_end_and_closes() -> None:
    hub = finished_hub(2)
    runner = FakeRunner(status_of("done", scenes_done=2))
    events = sse_of(follow_job(runner, hub, 1, 0))
    assert [identifier for identifier, _ in events] == ["0-1", "1-1", "1-2", "1-3"]
    assert [event["type"] for _, event in events] == ["state", "scene", "scene", "end"]


@pytest.mark.parametrize(("after", "ids"), [(0, ["1-1", "1-2", "1-3"]), (1, ["1-2", "1-3"]), (2, ["1-3"])])
def test_replay_resumes_after_the_given_seq(after: int, ids: list[str]) -> None:
    hub = finished_hub(2)
    events = sse_of(follow_job(FakeRunner(status_of("done")), hub, 1, after))
    assert [identifier for identifier, _ in events[1:]] == ids


def test_a_subscriber_that_fell_behind_the_buffer_gets_the_snapshot_and_the_retained_events() -> None:
    hub = finished_hub(count=6, limit=3)
    events = sse_of(follow_job(FakeRunner(status_of("done")), hub, 1, 0))
    assert [identifier for identifier, _ in events] == ["0-1", "1-5", "1-6", "1-7"]


def test_with_no_job_the_stream_is_the_snapshot_then_an_end_and_both_use_job_zero() -> None:
    events = sse_of(follow_job(FakeRunner(), JobEvents(), None, 0))
    assert [(identifier, event["type"], event["state"]) for identifier, event in events] == [
        ("0-1", "state", "idle"),
        ("0-2", "end", "idle"),
    ]


def test_a_reserved_slot_that_is_given_back_ends_the_stream_but_a_live_one_does_not() -> None:
    runner = FakeRunner(status_of("starting", total=0), active=True)
    stream = follow_job(runner, JobEvents(), None, 0, keepalive=0.0)
    assert sse_of(take(stream, 1))[0][0] == "0-1"
    assert next(stream) == KEEPALIVE_COMMENT  # still starting: no end
    runner.status = JobStatus()
    ended = sse_of(list(stream))
    assert [(identifier, event["type"]) for identifier, event in ended] == [("0-2", "end")]


def test_a_keepalive_comment_goes_out_at_the_injected_interval_and_the_stream_ends_with_end() -> None:
    hub = JobEvents()
    hub.add(scene_event(1))
    runner = FakeRunner(status_of("running"), active=True)
    stream = follow_job(runner, hub, 1, 1, keepalive=0.0)
    first = take(stream, 3)
    assert sse_of(first[:1])[0][0] == "0-1"
    assert first[1:] == [KEEPALIVE_COMMENT, KEEPALIVE_COMMENT]
    runner.status = status_of("done")
    hub.finish(runner.status)
    rest = list(stream)
    assert [event["type"] for _, event in sse_of(rest)] == ["end"]
    assert [identifier for identifier, _ in sse_of(rest)] == ["1-2"]


def test_a_stream_started_before_the_job_begins_follows_it_from_its_first_event() -> None:
    hub = finished_hub(1)  # an older job 1 that must not be replayed
    runner = FakeRunner(status_of("starting"), active=True)
    stream = follow_job(runner, hub, None, 0, keepalive=0.0)
    take(stream, 1)
    assert next(stream) == KEEPALIVE_COMMENT
    hub.add(scene_event(1))
    hub.finish(status_of("done"))
    rest = sse_of(list(stream))
    assert [identifier for identifier, _ in rest] == ["2-1", "2-2"]


def test_the_subscriber_holds_no_lock_while_the_consumer_has_the_stream() -> None:
    hub = JobEvents()
    hub.add(scene_event(1))
    stream = follow_job(FakeRunner(status_of("running"), active=True), hub, 1, 0)
    take(stream, 2)  # suspended after yielding
    writer = threading.Thread(target=lambda: hub.add(scene_event(2)))
    writer.start()
    writer.join(5)
    assert not writer.is_alive()
    stream.close()


def test_shutdown_wakes_a_waiting_stream_and_it_ends() -> None:
    hub = JobEvents()
    hub.add(scene_event(1))
    stream = follow_job(FakeRunner(status_of("running"), active=True), hub, 1, 1, keepalive=30.0, poll=30.0)
    take(stream, 1)
    done = threading.Event()
    seen: list[bytes] = []

    def drain() -> None:
        seen.extend(stream)
        done.set()

    thread = threading.Thread(target=drain)
    thread.start()
    hub.close()
    assert done.wait(5)
    thread.join(5)
    assert seen == []


def test_every_chunk_is_one_formatted_event_or_the_keepalive() -> None:
    hub = finished_hub(1)
    chunks = list(follow_job(FakeRunner(status_of("done")), hub, 1, 0))
    assert chunks[0] == format_sse(0, {"seq": 1, "type": "state", **current_job_json(status_of("done"), hub.latest_events())})
