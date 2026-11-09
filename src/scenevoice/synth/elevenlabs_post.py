from scenevoice.synth.urllib_post import _post_with


def elevenlabs_post(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> bytes:
    """POST body to url for ElevenLabs; only an HTTP 200 response is accepted."""
    return _post_with(
        url, headers, body, timeout, label="ElevenLabs", expect_status=200
    )
