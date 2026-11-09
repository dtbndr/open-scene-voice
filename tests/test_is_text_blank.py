import pytest

from scenevoice.synth.is_text_blank import is_text_blank


@pytest.mark.parametrize("text", ["", " ", "   ", "\n", " \n\t ", "　"])
def test_blank(text):
    assert is_text_blank(text) is True


@pytest.mark.parametrize(
    "text", ["\u001c", "\u001c ", "\u001d", "\u001e", "\u001f", " \u001f ", "a", " a "]
)
def test_not_blank(text):
    assert is_text_blank(text) is False
