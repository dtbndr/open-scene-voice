from difflib import SequenceMatcher

import pytest

from scenevoice.align import match_scene, matched_indexes, split_sentences, word_tokens


def heard_pairs(text: str, starts: list[float]) -> list[tuple[str, float]]:
    tokens = text.split()
    assert len(tokens) == len(starts)
    return list(zip(tokens, starts, strict=True))


def seq(text: str) -> list[tuple[str, float]]:
    tokens = text.split()
    return [(t, float(i)) for i, t in enumerate(tokens)]


def test_tie_example_matches_only_the_cat() -> None:
    script = "the cat and the dog".split()
    heard = "the dog and the cat".split()
    assert matched_indexes(script, heard) == {0: 3, 1: 4}


def test_tie_example_sentence_is_below_threshold() -> None:
    assert match_scene(["The cat and the dog."], seq("the dog and the cat")) == [None]


def test_worked_example_scene_1() -> None:
    heard = [
        ("welcome", 0.23999999865889549),
        ("back", 0.62),
        ("today", 1.2344),
        ("we", 1.6),
        ("start", 1.86),
    ]
    assert match_scene(["Welcome back.", "Today we start."], heard) == [240, 1234]


def test_worked_example_scene_2() -> None:
    heard = [
        ("keep", 0.12),
        ("it", 0.3),
        ("simple", 0.5),
        ("sue", 1.9),
        ("you", 2.1),
        ("nexus", 2.4),
    ]
    result = match_scene(["Keep it simple.", "See you next time."], heard)
    assert result == [120, None]


@pytest.mark.parametrize(
    ("script", "heard"),
    [
        ("the cat and the dog", "the dog and the cat"),
        ("a b c d e f", "x a b y c d e z f"),
        ("a a a b a a", "a a b a a a a"),
        ("one two three", "four five six"),
        ("", "a b"),
        ("a b", ""),
    ],
)
def test_matched_indexes_agrees_with_get_matching_blocks(script: str, heard: str) -> None:
    s, h = script.split(), heard.split()
    expected = {
        block.a + k: block.b + k
        for block in SequenceMatcher(None, s, h, autojunk=False).get_matching_blocks()
        for k in range(block.size)
    }
    assert matched_indexes(s, h) == expected


def test_autojunk_is_off_for_long_scenes() -> None:
    # 211 heard tokens with a very frequent one: autojunk=True would give {2: 0}.
    script = ["x", "x", "b"]
    heard = ["b"] + ["x"] * 210
    assert matched_indexes(script, heard) == {0: 1, 1: 2}


def test_word_moved_across_a_sentence_boundary_still_matches() -> None:
    sentences = ["a b c d.", "e f g h."]
    heard = seq("a b c e d f g h")
    result = match_scene(sentences, heard)
    # Whole-scene matching: d (heard index 4) is matched, e (index 3) is not,
    # so the second sentence starts at f (heard index 5), not at e.
    assert result == [0, 5000]


def test_start_comes_from_first_matched_token_of_the_sentence() -> None:
    # first matched token of the scene is 'a' at 0.5 s; sentence 2 must use its own.
    heard = [("a", 0.5), ("b", 1.0), ("c", 2.0), ("d", 3.0)]
    assert match_scene(["a b.", "c d."], heard) == [500, 2000]


def test_first_matched_token_skips_unmatched_leading_token() -> None:
    heard = [("b", 1.0), ("c", 2.0)]
    assert match_scene(["a b c."], heard) == [1000]


@pytest.mark.parametrize(
    ("sentence", "heard", "expected"),
    [
        ("a b c d.", "a b x y", 0),
        ("a b c.", "a x y", None),
        ("a b.", "a x", 0),
        ("a b c d.", "a x y z", None),
    ],
)
def test_threshold_boundaries(sentence: str, heard: str, expected: int | None) -> None:
    assert match_scene([sentence], seq(heard)) == [expected]


def test_zero_token_sentence_is_unmatched_before_threshold() -> None:
    sentences = split_sentences("Hello. ... Next.")
    assert sentences == ["Hello.", "...", "Next."]
    assert [word_tokens(s) for s in sentences] == [["hello"], [], ["next"]]
    heard = [("hello", 0.1), ("next", 0.9)]
    result = match_scene(sentences, heard)
    assert result == [100, None, 900]
    assert len(result) == 3


def test_all_zero_token_scene_is_all_none() -> None:
    assert match_scene(["..."], [("a", 0.0)]) == [None]


def test_no_sentences_gives_empty_list() -> None:
    assert match_scene([], [("a", 0.0)]) == []


def test_unrepresentable_start_gives_none() -> None:
    assert match_scene(["a."], [("a", float("inf"))]) == [None]
