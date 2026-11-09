from scenevoice.synth.redact_secret import redact_secret

SECRET = "sk-distinct-123\n"


def test_raw_and_stripped_forms_are_replaced():
    message = "bad key 'sk-distinct-123\n' and sk-distinct-123 again sk-distinct-123"
    out = redact_secret(message, SECRET)
    assert "sk-distinct-123" not in out
    assert out.count("[redacted]") == 3


def test_message_without_secret_is_unchanged():
    assert redact_secret("scene 1: nothing here", SECRET) == "scene 1: nothing here"


def test_raw_form_with_padding_is_replaced_whole():
    out = redact_secret("x  key \n y", "  key \n")
    assert out == "x[redacted] y"


def test_empty_whitespace_and_none_secret_leave_message_unchanged():
    message = "keep  \n this"
    for secret in ("", "  \n\t", None):
        assert redact_secret(message, secret) == message
