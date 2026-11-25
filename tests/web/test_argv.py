import sys
from pathlib import Path

import pytest

from scenevoice.keys.key_names import KEY_NAMES
from scenevoice.web import (
    build_align_argv,
    build_beats_argv,
    build_pack_argv,
    build_synth_argv,
    child_env,
    cli_argv_prefix,
    launch_message,
    reveal_argv,
)
from scenevoice.web.build_pack_zip import PACK_OUTPUTS
from scenevoice.web.common_settings import common_settings
from scenevoice.web.pack_output_names import pack_output_names
from scenevoice.web.record_item import RecordItem
from scenevoice.web.restart_names import RESTART_FIXED, restart_names

PLAN = Path("/tmp/launch/plan-x.json")
DIR = Path("/ws/my-video")


def test_the_whole_argument_list_is_align_progress_json_then_the_plan_file_and_the_project_folder():
    assert build_align_argv(PLAN, DIR) == ["align", "--progress", "json", "/tmp/launch/plan-x.json", "/ws/my-video"]


def test_relative_paths_are_made_absolute_and_the_plan_is_the_counted_file_not_the_script():
    result = build_align_argv(Path("plan.json"), Path("here"))
    assert result[3].startswith("/") and result[3].endswith("/plan.json") and result[4].startswith("/")


SCRIPT = Path("/tmp/launch/script-x.md")
CANDIDATE = Path("/ws/my-video/.write-beats-ab12.tmp")


def test_the_whole_argument_list_is_beats_the_script_copy_out_the_candidate_model_in_the_equals_form_then_progress_json():
    assert build_beats_argv(SCRIPT, CANDIDATE, "openai/gpt-x") == [
        "beats", "/tmp/launch/script-x.md", "--out", "/ws/my-video/.write-beats-ab12.tmp", "--model=openai/gpt-x", "--progress", "json",
    ]


def test_relative_paths_are_made_absolute_and_a_model_that_starts_with_a_dash_stays_a_value():
    result = build_beats_argv(Path("s.md"), Path("c.tmp"), "-x")
    assert result[1].startswith("/") and result[3].startswith("/") and result[4] == "--model=-x"


PLAN_build_pack_argv = Path("/tmp/launch/plan-x.json")
DIR_build_pack_argv = Path("/ws/my-video")


def test_the_whole_argument_list_is_pack_for_resolve_with_json_progress_then_the_plan_file_and_the_folder():
    assert build_pack_argv(PLAN_build_pack_argv, DIR_build_pack_argv) == ["pack", "--editor", "resolve", "--progress", "json", "/tmp/launch/plan-x.json", "/ws/my-video"]


def test_relative_paths_are_made_absolute():
    result = build_pack_argv(Path("plan.json"), Path("here"))
    assert result[5].startswith("/") and result[6].startswith("/")


PLAN_build_synth_argv = Path("/tmp/launch/plan-x.json")
DIR_build_synth_argv = Path("/ws/my-video")


def argv(**changes):
    options = {"voice": "Leda", "model": "gem", "language": None, "instruction": None, "scene": None, **changes}
    return build_synth_argv(PLAN_build_synth_argv, DIR_build_synth_argv, **options)


def test_the_whole_argument_list_in_order_with_absolute_paths_and_the_equals_form():
    assert argv(language="en-GB", instruction="Calm", scene=3) == [
        "synth", "/tmp/launch/plan-x.json", "--out", "/ws/my-video", "--voice=Leda", "--model=gem",
        "--language=en-GB", "--instruction=Calm", "--scene=3", "--progress", "json",
    ]


def test_a_null_language_or_instruction_or_scene_leaves_its_flag_out():
    assert argv() == ["synth", str(PLAN_build_synth_argv), "--out", str(DIR_build_synth_argv), "--voice=Leda", "--model=gem", "--progress", "json"]


def test_a_value_that_starts_with_a_dash_or_holds_spaces_and_quotes_stays_one_value():
    value = "--out /etc/passwd; \"rm\" $(x) 'y'"
    result = argv(voice="-v", instruction=value)
    assert "--voice=-v" in result and f"--instruction={value}" in result
    assert len(result) == 9


def test_a_relative_directory_is_made_absolute():
    relative = build_synth_argv(Path("plan.json"), Path("here"), voice="V", model="m", language=None, instruction=None, scene=None)
    assert relative[1].startswith("/") and relative[3].startswith("/")


def test_default_prefix_is_isolated_utf8_module_run():
    assert cli_argv_prefix() == [sys.executable, "-I", "-X", "utf8", "-m", "scenevoice"]


def test_darwin_opens_the_directory_with_open_and_linux_with_xdg_open():
    assert reveal_argv("darwin", "/ws/my-video") == ["open", "/ws/my-video"]
    assert reveal_argv("linux", "/ws/my-video") == ["xdg-open", "/ws/my-video"]
    assert reveal_argv("linux2", "/ws/my-video") == ["xdg-open", "/ws/my-video"]


@pytest.mark.parametrize("platform", ["win32", "cygwin", "freebsd14", "", "Darwin"])
def test_any_other_platform_has_no_argv(platform):
    assert reveal_argv(platform, "/ws/my-video") is None


@pytest.mark.parametrize("directory", ["ws/my-video", "", "-a", "./x"])
def test_a_directory_that_is_not_absolute_is_refused_before_any_argv_is_built(directory):
    with pytest.raises(ValueError):
        reveal_argv("darwin", directory)
    with pytest.raises(ValueError):
        reveal_argv("win32", directory)


PASSED = {
    "HTTPS_PROXY": "http://proxy:3128",
    "SSL_CERT_FILE": "/certs/ca.pem",
    "SCENEVOICE_KEYS_FILE": "/k/keys.env",
    "XDG_CONFIG_HOME": "/x",
    "APPDATA": "/a",
    "HOME": "/h",
}


@pytest.mark.parametrize("name", KEY_NAMES)
def test_each_key_name_is_removed(name):
    assert name not in child_env({name: "v", "HOME": "/h"})


def test_everything_else_passes_through_and_input_is_not_mutated():
    source = {**PASSED, **{name: "v" for name in KEY_NAMES}}
    before = dict(source)
    assert child_env(source) == PASSED
    assert source == before


def item(ordinal, voice="V", model="m", language=None, instruction=None):
    return RecordItem(ordinal, "0" * 64, voice, model, language, instruction, None)


def test_entries_that_agree_give_the_shared_settings_with_nulls_carried():
    assert common_settings((item(1), item(2))) == {"voice": "V", "model": "m", "language": None, "instruction": None}


def test_any_disagreement_or_no_entry_gives_none():
    assert common_settings((item(1), item(2, voice="W"))) is None
    assert common_settings((item(1), item(2, instruction="soft"))) is None
    assert common_settings(()) is None


def test_only_the_two_pack_outputs_present_in_the_listing_are_named_in_the_pack_order():
    listing = ["resolve_timeline.otio", "synth_record.json", "line_timings.json", "scene_manifest.csv", "script.md", "audio"]
    assert pack_output_names(listing) == ["scene_manifest.csv", "resolve_timeline.otio"]


def test_names_missing_from_the_listing_are_not_invented_and_other_spellings_are_not_matched():
    assert pack_output_names(["Scene_Manifest.csv", "resolve_timeline.otio.bak"]) == []


def test_the_fixed_names_are_the_record_the_line_markers_and_the_pack_outputs_shared_with_the_pack_constant():
    assert RESTART_FIXED == ("synth_record.json", "line_timings.json", *PACK_OUTPUTS)
    assert set(RESTART_FIXED) == {"synth_record.json", "line_timings.json", "scene_manifest.csv", "resolve_timeline.otio"}


def test_only_the_exact_names_are_allowed_and_the_wavs_come_last():
    project = [*RESTART_FIXED, "script.md", "beats.json", "audio", ".write-x.tmp", "Synth_Record.json", "001.wav"]
    audio = ["010.wav", "001.wav", "1.wav", "001.wav.bak", ".write-001.wav.tmp", "002.WAV", "nested", "0001234567.wav", "0001.wav"]
    assert restart_names(project, audio) == [*RESTART_FIXED, "audio/0001.wav", "audio/001.wav", "audio/010.wav"]


def test_names_missing_from_the_listing_are_not_invented():
    assert restart_names(["script.md"], []) == []


LINK = "http://127.0.0.1:47615/?token=abc"


def test_the_four_lines_come_in_order_with_the_link():
    assert launch_message(LINK, []) == [
        "SceneVoice is running.",
        f"Open it here: {LINK}",
        "Keep this window open while you work. Closing it stops SceneVoice.",
        "To stop on purpose, press Control-C.",
    ]


def test_ignored_variable_names_get_one_extra_line_and_never_a_value():
    lines = launch_message(LINK, ["OPENROUTER_API_KEY", "ELEVENLABS_API_KEY"])
    assert len(lines) == 5
    assert lines[:4] == launch_message(LINK, [])
    assert "OPENROUTER_API_KEY, ELEVENLABS_API_KEY" in lines[4]
    assert "scenevoice keys set" in lines[4]
