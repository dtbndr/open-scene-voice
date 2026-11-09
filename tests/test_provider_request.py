import dataclasses
import json

import pytest

from scenevoice.synth import ProviderRequest, make_vertex_provider

ENV = {
    "GOOGLE_CLOUD_PROJECT": "my-proj",
    "GOOGLE_CLOUD_LOCATION": "us-central1",
    "VERTEX_AUTHORIZATION_KEY": "SECRET-KEY-123",
}
MODEL = "gemini-3.8-flash-tts"


class FakePost:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        return json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "audio/wav", "data": "AAAA"}}]}}]}).encode()


def test_fields_in_order():
    names = [f.name for f in dataclasses.fields(ProviderRequest)]
    assert names == ["body", "previous_text", "next_text", "voice", "language", "instruction"]


def test_request_is_frozen():
    request = ProviderRequest("b", None, None, "Kore", "en-US", None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.body = "other"  # type: ignore[misc]


def send(request):
    post = FakePost()
    provider = make_vertex_provider(ENV, MODEL, post=post)
    try:
        provider(request)
    except Exception:
        pass
    assert len(post.calls) == 1
    return post.calls[0]


def test_vertex_ignores_neighbour_fields():
    bare = send(ProviderRequest("body", None, None, "Kore", "en-US", "Say:"))
    full = send(ProviderRequest("body", "before", "after", "Kore", "en-US", "Say:"))
    assert bare == full


def test_vertex_sends_body_voice_language_and_style_in_the_body():
    _, _, payload, _ = send(ProviderRequest("hello body", "p", "n", "Charon", "en-GB", "Calm"))
    text = payload.decode()
    for part in ("hello body", "Charon", "en-GB", "Calm"):
        assert part in text
    assert "\"p\"" not in text and "\"n\"" not in text


def test_vertex_without_language_raises_provider_error():
    from scenevoice.synth import ProviderError

    provider = make_vertex_provider(ENV, MODEL, post=FakePost())
    with pytest.raises(ProviderError, match="Vertex request has no language"):
        provider(ProviderRequest("b", None, None, "Kore", None, None))
