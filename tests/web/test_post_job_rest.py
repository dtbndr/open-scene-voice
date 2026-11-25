import json
import shutil
from pathlib import Path

import pytest
from detail_helper import passing, put_record, put_wavs
from job_runner_helper import wait_final, wait_started
from post_job_helper import (
    BODIES3,
    MODEL,
    SCRIPT3,
    WAVS,
    JobBed,
    confirm_for,
    synth_rest,
)

from scenevoice.web import build_synth_argv

CHANGED = "The script or settings changed since you confirmed. Check the numbers and confirm again."
NOTHING = "Nothing has been voiced yet."
MISMATCH = "What was voiced does not match this script or these settings. Choose Start again."
DIFFER = "One script uses one voice and model. These settings differ from the ones already used."
ALL_VOICED = "Every scene is already voiced."
CANCELLED = "Cancelled before it started. Nothing was spent."
NOTHING_SPENT_STOPPING = "SceneVoice is stopping."


def done_line(scene: int, total: int = 3) -> str:
    return json.dumps({"command": "synth", "event": "scene", "message": "done", "state": "done", "scene": scene, "total": total})


def bed_with(stub_cli, tmp_path, voiced=(1,), bodies=BODIES3, script=SCRIPT3, **spec):
    bed = JobBed(stub_cli(**spec), tmp_path, run=passing(bodies))
    bed.save_script(script)
    if voiced:
        put_wavs(bed.project, {n: WAVS.get(n, b"wav-%d" % n) for n in voiced})
        put_record(bed.project, bodies, {n: WAVS.get(n, b"wav-%d" % n) for n in voiced})
    return bed


def rest_body(bodies=BODIES3[1:], **changes):
    return synth_rest(bodies, **{"confirm": confirm_for(SCRIPT3, bodies), **changes})


# --- rest ------------------------------------------------------------------------------------------------------------


def test_rest_runs_one_child_per_unvoiced_scene_in_order_over_the_one_plan_file_with_the_records_settings(stub_cli, tmp_path):
    bed = bed_with(stub_cli, tmp_path, stderr_lines=[done_line(1)])
    response, parsed = bed.post(rest_body())
    assert response.status == 202 and parsed["job"]["total"] == 2 and parsed["job"]["mode"] == "rest"
    assert wait_final(bed.runner).state == "done"
    calls = bed.children()
    plan_files = {call["argv"][1] for call in calls}
    assert len(calls) == 2 and len(plan_files) == 1
    assert [call["argv"] for call in calls] == [
        build_synth_argv(Path(next(iter(plan_files))), bed.project, voice="Leda", model=MODEL, language="en-GB", instruction=None, scene=n)
        for n in (2, 3)
    ]
    assert bed.runner.current().scenes_done == 2 and bed.launch_files() == []


def test_the_rest_echo_is_the_unvoiced_count_their_characters_the_recorded_model_and_the_revision(stub_cli, tmp_path):
    bed = bed_with(stub_cli, tmp_path)
    for wrong in (confirm_for(SCRIPT3, BODIES3), {**confirm_for(SCRIPT3, BODIES3[1:]), "model": "other"}, {**confirm_for(SCRIPT3, BODIES3[1:]), "characters": 1}):
        assert bed.error(rest_body(confirm=wrong))[:2] == (409, "changed")
    assert bed.error(rest_body(confirm={**confirm_for(SCRIPT3, BODIES3[1:]), "revision": "0" * 64}))[:2] == (409, "changed")
    assert bed.children() == []


def test_rest_never_takes_the_clients_settings_a_differing_one_is_refused_and_nothing_is_spawned(stub_cli, tmp_path):
    bed = bed_with(stub_cli, tmp_path)
    assert bed.error(rest_body(voice="Other")) == (409, "not_allowed", DIFFER)
    assert bed.error(rest_body(model="other-model", confirm=confirm_for(SCRIPT3, BODIES3[1:], "other-model"))) == (409, "not_allowed", DIFFER)
    assert bed.children() == []
    response, _ = bed.post(rest_body(voice="Leda", model=MODEL, language="en-GB"))
    assert response.status == 202
    wait_final(bed.runner)


def nothing_voiced(bed):
    shutil.rmtree(bed.project / "audio")
    (bed.project / "synth_record.json").unlink()


REST_REFUSALS = {
    "nothing-voiced": (nothing_voiced, NOTHING),
}


@pytest.mark.parametrize("name", REST_REFUSALS)
def test_rest_refuses_through_the_one_availability_function_before_anything_spawns(stub_cli, tmp_path, name):
    setup, message = REST_REFUSALS[name]
    bed = bed_with(stub_cli, tmp_path)
    setup(bed)
    unvoiced = BODIES3 if name == "nothing-voiced" else BODIES3[1:]
    body = rest_body(unvoiced if name != "every-scene-voiced" else [], confirm=confirm_for(SCRIPT3, [] if name == "every-scene-voiced" else unvoiced))
    assert bed.error(body) == (409, "not_allowed", message)
    assert bed.children() == [] and bed.runner.current().state == "idle" and bed.launch_files() == []


def test_a_failed_child_stops_the_rest_with_no_later_child_and_counts_the_scenes_completed(stub_cli, tmp_path):
    bed = bed_with(stub_cli, tmp_path, exit_code=1)
    bed.post(rest_body())
    final = wait_final(bed.runner)
    assert (final.state, final.scenes_done, final.total) == ("failed", 0, 2)
    assert len(bed.children()) == 1


def test_cancel_during_a_child_ends_cancelled_with_no_later_child(stub_cli, tmp_path):
    bed = bed_with(stub_cli, tmp_path, sleep=30, sigint="exit", sigint_exit_code=130)
    bed.post(rest_body())
    wait_started(bed.stub)
    bed.runner.cancel()
    final = wait_final(bed.runner)
    assert (final.state, final.scenes_done) == ("cancelled", 0)
    assert len(bed.children()) == 1
