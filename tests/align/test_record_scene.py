from scenevoice.align import SceneTimings, record_scene, split_sentences
from scenevoice.pack import LineTiming
from scenevoice.synth import Alignment, PlanScene

SHA = "ab" * 32


def _alignment(elements: list[str], starts: list[float]) -> Alignment:
    return Alignment(tuple(elements), tuple(starts), tuple(starts))


def _per_char(body: str) -> Alignment:
    return _alignment(list(body), [i / 10 for i in range(len(body))])


def _scene(body: str, ordinal: int = 1) -> PlanScene:
    return PlanScene(ordinal, "Title", body)


def _timings(result: SceneTimings | str) -> SceneTimings:
    assert isinstance(result, SceneTimings)
    return result


def test_mini_example() -> None:
    alignment = _alignment(
        ["Hi", " there.", " ", "Go", " on."], [0.23999999865889549, 0.5, 1.1, 1.2344, 1.6]
    )
    result = _timings(record_scene(_scene("Hi there. Go on.", 4), SHA, alignment))
    assert result.ordinal == 4
    assert result.sha256 == SHA
    assert result.lines == [LineTiming("Hi there.", 240), LineTiming("Go on.", 1234)]


def test_offset_inside_multi_code_point_element_takes_that_elements_start() -> None:
    alignment = _alignment(["Hi. ", "Go", "od."], [0.1, 0.2, 0.3])
    result = _timings(record_scene(_scene("Hi. Good."), SHA, alignment))
    assert [line.start_ms for line in result.lines] == [100, 200]
    alignment = _alignment(["Hi.", " ", "Go.", " Fine."], [0.1, 0.2, 0.3, 0.4])
    result = _timings(record_scene(_scene("Hi. Go. Fine."), SHA, alignment))
    assert [line.start_ms for line in result.lines] == [100, 300, 400]


def test_empty_elements_are_never_chosen() -> None:
    alignment = _alignment(
        ["", "Hi.", "", " ", "", "Go.", ""], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    )
    result = _timings(record_scene(_scene("Hi. Go."), SHA, alignment))
    assert [line.start_ms for line in result.lines] == [200, 600]


def test_repeated_sentence_takes_second_start() -> None:
    result = _timings(record_scene(_scene("Yes. Yes."), SHA, _per_char("Yes. Yes.")))
    assert [line.start_ms for line in result.lines] == [0, 500]


def test_crlf_body_offsets_count_the_cr() -> None:
    body = "First line.\r\nSecond line."
    result = _timings(record_scene(_scene(body), SHA, _per_char(body)))
    assert [line.start_ms for line in result.lines] == [0, 1300]


def test_zero_token_sentence_has_null_start() -> None:
    body = "Hello. ... Next."
    result = _timings(record_scene(_scene(body), SHA, _per_char(body)))
    assert [line.text for line in result.lines] == ["Hello.", "...", "Next."]
    assert [line.start_ms for line in result.lines] == [0, None, 1100]


def test_zero_token_sentence_start_is_not_converted() -> None:
    body = "Hello. ... Next."
    starts = [i / 10 for i in range(len(body))]
    starts[7] = 1e306
    result = _timings(record_scene(_scene(body), SHA, _alignment(list(body), starts)))
    assert result.lines[1].start_ms is None


def test_overflow_on_sentence_start_returns_reason() -> None:
    body = "Hi. Go."
    starts = [i / 10 for i in range(len(body))]
    starts[4] = 1e306
    result = record_scene(_scene(body), SHA, _alignment(list(body), starts))
    assert isinstance(result, str)
    assert "\n" not in result
    assert not result.startswith("FAIL ")


def test_overflow_on_non_starting_element_is_ignored() -> None:
    body = "Hi. Go."
    starts = [i / 10 for i in range(len(body))]
    starts[1] = 1e306
    result = _timings(record_scene(_scene(body), SHA, _alignment(list(body), starts)))
    assert [line.start_ms for line in result.lines] == [0, 400]


def test_lines_text_matches_split_sentences() -> None:
    body = "Dr. Smith arrived. He sat down."
    result = _timings(record_scene(_scene(body), SHA, _per_char(body)))
    assert [line.text for line in result.lines] == split_sentences(body)
