import pytest

from scenevoice.align import word_tokens


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("word—word", ["wordword"]),
        ("well-known", ["wellknown"]),
        ("3.5", ["35"]),
        ("Hello,", ["hello"]),
        (" burning,", ["burning"]),
        ("don't", ["don't"]),
        ("—", []),
        ("...", []),
        ("", []),
        ("Hello world", ["hello", "world"]),
        ("two words", ["two", "words"]),
    ],
)
def test_token_table(text: str, tokens: list[str]) -> None:
    assert word_tokens(text) == tokens


def test_curly_apostrophe_is_dropped_not_folded() -> None:
    assert word_tokens("don’t") == ["dont"]
    assert word_tokens("don't") == ["don't"]
    assert word_tokens("don’t") != word_tokens("don't")


def test_accented_letters_are_dropped() -> None:
    assert word_tokens("café") == ["caf"]


def test_kelvin_sign_lowercases_to_k() -> None:
    assert word_tokens("K") == ["k"]


def test_dotted_capital_i_gives_i() -> None:
    assert word_tokens("İ") == ["i"]


def test_sharp_s_is_dropped() -> None:
    assert word_tokens("ß") == []
    assert word_tokens("aßb") == ["ab"]


@pytest.mark.parametrize("ch", ["\u001c", "\u001d", "\u001e", "\u001f"])
def test_separator_controls_do_not_split(ch: str) -> None:
    assert word_tokens(f"a{ch}b") == ["ab"]
