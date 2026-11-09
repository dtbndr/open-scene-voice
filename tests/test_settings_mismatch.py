from scenevoice.synth.record_entry import RecordEntry
from scenevoice.synth.record_settings import RecordSettings
from scenevoice.synth.regen_notes import missing_entry_note, missing_record_note
from scenevoice.synth.settings_mismatch import settings_mismatch

HEAD = "scene 2 settings differ from synth_record.json: "


def entry(voice="V", model="M", language="en-GB", instruction=None):
    return RecordEntry(2, "0" * 64, voice, model, language, instruction, None)


def passed(voice="V", model="M", language="en-GB", instruction=None):
    return RecordSettings(voice, model, language, instruction)


def test_all_equal_is_none():
    assert settings_mismatch(2, entry(instruction="calm"), passed(instruction="calm")) is None


def test_voice_only():
    got = settings_mismatch(2, entry(voice="Callirrhoe"), passed(voice="Charon"))
    assert got == HEAD + 'voice recorded "Callirrhoe", passed "Charon"'


def test_voice_and_model():
    got = settings_mismatch(2, entry(voice="A", model="C"), passed(voice="B", model="D"))
    assert got == HEAD + 'voice recorded "A", passed "B"; model recorded "C", passed "D"'


def test_all_four_in_order():
    got = settings_mismatch(
        2,
        entry("A", "C", "en-GB", "x"),
        passed("B", "D", "en-US", "y"),
    )
    assert got == HEAD + (
        'voice recorded "A", passed "B"; model recorded "C", passed "D"; '
        'language recorded "en-GB", passed "en-US"; instruction recorded "x", passed "y"'
    )


def test_instruction_recorded_none():
    got = settings_mismatch(2, entry(), passed(instruction="calm"))
    assert got == HEAD + 'instruction recorded (none), passed "calm"'


def test_literal_none_text_stays_distinct():
    got = settings_mismatch(2, entry(instruction="(none)"), passed())
    assert got == HEAD + 'instruction recorded "(none)", passed (none)'


def test_language_recorded_none():
    got = settings_mismatch(2, entry(language=None), passed(language="en-GB"))
    assert got == HEAD + 'language recorded (none), passed "en-GB"'


def test_line_break_runs_collapse_to_one_space():
    got = settings_mismatch(2, entry(instruction="a\r\nb\n\nc"), passed(instruction="z"))
    assert got == HEAD + 'instruction recorded "a b c", passed "z"'


def test_embedded_quote_shown_as_is():
    got = settings_mismatch(2, entry(instruction='say "hi"'), passed())
    assert got == HEAD + 'instruction recorded "say "hi"", passed (none)'


def test_long_value_not_truncated():
    long = "x" * 5000
    got = settings_mismatch(2, entry(instruction=long), passed())
    assert got == HEAD + f'instruction recorded "{long}", passed (none)'


def test_case_and_spaces_count():
    assert settings_mismatch(2, entry(instruction="calm"), passed(instruction="Calm")) == (
        HEAD + 'instruction recorded "calm", passed "Calm"'
    )
    assert settings_mismatch(2, entry(instruction="calm"), passed(instruction="calm ")) == (
        HEAD + 'instruction recorded "calm", passed "calm "'
    )


def test_n_is_the_integer_as_given():
    got = settings_mismatch(10, entry(voice="A"), passed(voice="B"))
    assert got == (
        'scene 10 settings differ from synth_record.json: voice recorded "A", passed "B"'
    )


def test_note_texts():
    assert missing_record_note(2) == (
        "no settings recorded for scene 2 (synth_record.json is missing); settings not checked"
    )
    assert missing_entry_note(2) == (
        "no settings recorded for scene 2 in synth_record.json; settings not checked"
    )
