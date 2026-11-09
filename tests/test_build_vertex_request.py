import json

import pytest

from scenevoice.synth.build_vertex_request import build_vertex_request

MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]


def build(
    project="proj-1",
    location="global",
    key="k",
    body="Hello",
    voice="Kore",
    language="en-US",
    style=None,
    model="gemini-3.8-flash-tts",
):
    return build_vertex_request(project, location, key, body, voice, language, style, model)


def payload(**kwargs):
    _, _, raw = build(**kwargs)
    return json.loads(raw.decode("utf-8"))


def keys_anywhere(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys_anywhere(value)
    elif isinstance(node, list):
        for item in node:
            yield from keys_anywhere(item)


def test_url_matches_template():
    url, _, _ = build()
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/proj-1/locations/global"
        "/publishers/google/models/gemini-3.8-flash-tts:generateContent"
    )


def test_project_and_location_are_quoted():
    url, _, _ = build(project="a/b?c#d e", location="x/y?z#w v")
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/a%2Fb%3Fc%23d%20e"
        "/locations/x%2Fy%3Fz%23w%20v/publishers/google/models/"
        "gemini-3.8-flash-tts:generateContent"
    )


def test_headers_carry_key_and_content_type():
    _, headers, _ = build(key="secret-key")
    assert headers == {"X-goog-api-key": "secret-key", "Content-Type": "application/json"}


def test_body_has_exact_structure_without_style():
    assert payload(body="Say it", voice="Puck", language="de-DE") == {
        "contents": [{"role": "user", "parts": [{"text": "Say it"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "languageCode": "de-DE",
                "voiceConfig": {"voice": "Puck"},
            },
        },
    }


def test_body_has_exact_structure_with_style():
    assert payload(body="Say it", voice="Puck", language="de-DE", style="Slowly.") == {
        "contents": [
            {"role": "user", "parts": [{"text": "Say it", "speechMetadata": {"style": "Slowly."}}]}
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "languageCode": "de-DE",
                "voiceConfig": {"voice": "Puck"},
            },
        },
    }


def test_language_code_and_voice_sit_under_speech_config():
    speech = payload(voice="Puck", language="de-DE")["generationConfig"]["speechConfig"]
    assert speech["languageCode"] == "de-DE"
    assert speech["voiceConfig"]["voice"] == "Puck"


def test_no_prebuilt_voice_config_or_system_instruction_is_sent():
    for style in (None, "Slowly."):
        names = set(keys_anywhere(payload(style=style)))
        assert "prebuiltVoiceConfig" not in names
        assert "systemInstruction" not in names  # NOT sent: rejected by the 3.8 model


def test_speech_metadata_absent_when_style_is_none():
    data = payload(style=None)
    assert "speechMetadata" not in set(keys_anywhere(data))
    # positive control: the same builder does emit it when a style is given
    assert "speechMetadata" in set(keys_anywhere(payload(style="x")))


def test_speech_metadata_is_sibling_of_text_in_first_part():
    data = payload(body="Say it", style="Say it slowly.")
    part = data["contents"][0]["parts"][0]
    assert part["text"] == "Say it"
    assert part["speechMetadata"] == {"style": "Say it slowly."}
    assert "speechMetadata" not in data
    assert "speechMetadata" not in data["generationConfig"]
    assert "speechMetadata" not in data["generationConfig"]["speechConfig"]
    assert "speechMetadata" not in data["contents"][0]


def test_empty_string_style_is_still_included():
    part = payload(style="")["contents"][0]["parts"][0]
    assert part["speechMetadata"] == {"style": ""}


def test_non_ascii_text_round_trips_unescaped():
    text = "Grüße 日本語 \U0001f600"
    _, _, raw = build(body=text)
    assert isinstance(raw, bytes)
    assert text.encode("utf-8") in raw
    assert json.loads(raw)["contents"][0]["parts"][0]["text"] == text


def test_body_is_sent_verbatim_without_composition():
    text = "  instruction line\n\nbody  "
    assert payload(body=text)["contents"][0]["parts"][0]["text"] == text


def test_non_ascii_style_round_trips_unescaped_and_unstripped():
    style = "  Sprich ruhig, 日本語 \U0001f600\n"
    _, _, raw = build(style=style)
    assert style.encode("utf-8").replace(b"\n", b"\\n") in raw
    assert json.loads(raw)["contents"][0]["parts"][0]["speechMetadata"]["style"] == style


def test_control_character_style_is_unmodified():
    style = "a\tb\x01c\x7fd e"
    assert payload(style=style)["contents"][0]["parts"][0]["speechMetadata"]["style"] == style


@pytest.mark.parametrize("model", MODELS)
def test_url_carries_the_model_in_the_path(model):
    url, _, _ = build(model=model)
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/proj-1/locations/global"
        f"/publishers/google/models/{model}:generateContent"
    )


def test_payload_and_headers_are_identical_for_both_models():
    flash_url, flash_headers, flash_raw = build(style="calm", model=MODELS[0])
    lite_url, lite_headers, lite_raw = build(style="calm", model=MODELS[1])
    assert flash_url != lite_url  # positive control: the model does change the URL
    assert flash_headers == lite_headers
    assert flash_raw == lite_raw
    assert json.loads(flash_raw) == json.loads(lite_raw)


def test_voice_beyond_the_original_two_reaches_the_payload():
    voice = payload(voice="Zubenelgenubi")["generationConfig"]["speechConfig"]["voiceConfig"]["voice"]
    assert voice == "Zubenelgenubi"
