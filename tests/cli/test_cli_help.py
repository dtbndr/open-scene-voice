"""`--help` text of every command: owner-facing phrases present, retired phrases absent."""

import pytest

from scenevoice.cli.main import main
from scenevoice.synth import MODELS, VOICES

FAILED_REPLY_SENTENCE = (
    "If the reply fails its checks or is cut off at the length limit, it is saved as raw text, "
    "the command exits 1, and the file is not usable beats. A paid call is used either way."
)


# command -> (phrases that must appear, phrases that must not)
HELP = {
    "synth": (
        [
            *MODELS, *VOICES, "--out", "--voice", "--model", "--scene", "--instruction",
            "TTS model (required, no default)", "exact match", "30 prebuilt", "no default",
            "--instruction=TEXT", "regenerates only scene N", "ElevenLabs voice ID",
            "language code, Gemini models only", "default for a Gemini model: en-GB",
            "delivery style instruction, Gemini models only",
            "the WAV files are written to DIR/audio", "checked against DIR/synth_record.json",
            "one provider call", "replaces DIR/audio/NNN.wav", "must already exist",
            "pass the original --voice", "again",
        ],
        ["output directory for the WAV files", "outputs do not record them", "standing instruction"],
    ),
    "pack": (
        ["[PLAN] DIR", "DIR", "--editor", "resolve", "WAV files in DIR/audio"],
        ["directory of WAV files", "next to the synthesized WAV files"],
    ),
    "align": (
        ["[PLAN] DIR", "OPENROUTER_API_KEY", "hosted", "line_timings.json", "synth_record.json"],
        [
            "one hosted transcription call per scene",
            "one hosted OpenRouter transcription call per scene",
        ],
    ),
    "beats": (
        [
            "OpenRouter", "script text is sent", "provider quota", "OPENROUTER_API_KEY",
            "never overwrites", "not part of the script",
        ],
        ["stdout"],
    ),
}


def help_of(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main([*argv, "--help"])
    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert captured.err == ""
    return captured.out, " ".join(captured.out.split())


@pytest.mark.parametrize("command", HELP)
def test_command_help(command, capsys):
    _, text = help_of([command], capsys)
    present, absent = HELP[command]
    for phrase in present:
        assert phrase in text, phrase
    for phrase in absent:
        assert phrase not in text, phrase


def test_synth_help_lists_four_models_and_thirty_voices():
    assert len(MODELS) == 4 and len(VOICES) == 30


def test_pack_help_shows_plan_dir_shape_on_the_first_line(capsys):
    raw, _ = help_of(["pack"], capsys)
    assert "[PLAN] DIR" in raw.splitlines()[0]


def test_beats_help_ends_with_the_failed_reply_sentence_once(capsys):
    _, text = help_of(["beats"], capsys)
    assert text.count(FAILED_REPLY_SENTENCE) == 1
    assert "The sidecar is not part of the script. " + FAILED_REPLY_SENTENCE in text


@pytest.mark.parametrize("command", ["pack", "align"])
def test_top_level_help_lists_the_command(command, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert command in capsys.readouterr().out


@pytest.mark.usefixtures("clean_env")
def test_draft_is_not_a_subcommand():
    with pytest.raises(SystemExit) as exc:
        main(["draft", "an idea", "--model", "m", "--out", "d.md"])
    assert exc.value.code == 2


NEW = 'from the environment, the key file or .env; see "scenevoice keys"'


OLD = "from the environment or .env"


@pytest.mark.parametrize("command", ["align", "beats"])
def test_key_help_names_the_key_file_and_keys_command(command, capsys):
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    assert NEW in text
    assert OLD not in text
