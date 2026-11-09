import copy

from scenevoice.pack import LineTiming, place_markers


def lt(ms):
    return LineTiming("x", ms)


def one(start, frames, starts, ordinal=1):
    return place_markers([(ordinal, start, frames, [lt(ms) for ms in starts])])


def test_contract_example_scene_one_and_two():
    placed, skipped = place_markers(
        [
            (1, 0, 50, [lt(0), lt(1000), lt(2120)]),
            (2, 60, 123, [lt(2500)]),
        ]
    )
    assert placed == [(0, 1, 0), (1, 1, 1), (24, 1, 2), (49, 1, 3), (60, 2, 0), (120, 2, 1)]
    assert skipped == []


def test_scene_marker_alone_when_no_lines():
    assert one(0, 50, []) == ([(0, 1, 0)], [])


def test_rounding_pair_1020_down_1021_up():
    assert one(0, 100, [1020])[0][1] == (24, 1, 1)
    assert one(0, 100, [1021])[0][1] == (25, 1, 1)


def test_cascade_10_10_11_lands_on_10_11_12():
    # start_ms 417 -> 10.008 frames -> 10; 459 -> 11.016 -> 11
    placed, skipped = one(0, 100, [417, 417, 459])
    assert [p[0] for p in placed[1:]] == [10, 11, 12]
    assert [p[2] for p in placed[1:]] == [1, 2, 3]
    assert skipped == []


def test_clamp_then_skip_second_line_on_last_frame():
    placed, skipped = one(0, 50, [5000, 6000])
    assert placed == [(0, 1, 0), (49, 1, 1)]
    assert skipped == [(1, 2)]


def test_line_wanting_last_frame_taken_by_earlier_line_is_skipped():
    placed, skipped = one(0, 50, [2040, 5000])
    assert (49, 1, 1) in placed
    assert skipped == [(1, 2)]


def test_1500_frame_case_skips_line_at_zero():
    placed, skipped = one(0, 1, [0])
    assert placed == [(0, 1, 0)]
    assert skipped == [(1, 1)]


def test_null_start_makes_no_marker_but_next_keeps_its_number():
    placed, skipped = one(0, 100, [1000, None, 2000])
    assert placed == [(0, 1, 0), (24, 1, 1), (48, 1, 3)]
    assert skipped == []


def test_tie_puts_scene_marker_first_so_it_never_moves():
    placed, _ = one(60, 50, [0])
    assert placed == [(60, 1, 0), (61, 1, 1)]


def test_non_monotonic_starts_process_by_wanted_frame_then_creation_order():
    # line 1 wants frame 1, line 2 wants frame 0 (taken by scene marker): line 2 goes first
    placed, _ = one(0, 100, [41, 0])
    assert placed == [(0, 1, 0), (1, 1, 2), (2, 1, 1)]


def test_equal_wanted_frames_follow_creation_order():
    placed, _ = one(0, 100, [1000, 1000])
    assert placed == [(0, 1, 0), (24, 1, 1), (25, 1, 2)]


def test_markers_of_different_clips_never_interact():
    placed, skipped = place_markers(
        [(1, 0, 3, [lt(0), lt(0), lt(0)]), (2, 13, 3, [lt(0)])]
    )
    assert (13, 2, 0) in placed and (14, 2, 1) in placed
    assert skipped == [(1, 3)]


def test_output_is_in_ascending_final_frame():
    placed, _ = one(0, 100, [2000, 500, 0, 1500])
    frames = [p[0] for p in placed]
    assert frames == sorted(frames)


def test_zero_length_lines_adds_nothing():
    assert one(0, 50, []) == ([(0, 1, 0)], [])


def test_skipped_is_in_plan_then_line_order_not_processing_order():
    # clip of 2 frames: scene at 0; line 1 (wanted 0) moves to 1; line 3 (wanted 0) is processed
    # before line 2 (wanted 1) and is skipped first, then line 2 is skipped.
    placed, skipped = one(0, 2, [0, 1000, 0])
    assert placed == [(0, 1, 0), (1, 1, 1)]
    assert skipped == [(1, 2), (1, 3)]


def test_skipped_across_scenes_is_in_plan_order():
    _, skipped = place_markers(
        [(1, 0, 1, [lt(0)]), (2, 11, 2, [lt(0), lt(0), lt(0)])]
    )
    assert skipped == [(1, 1), (2, 2), (2, 3)]


def test_deterministic_and_inputs_not_mutated():
    clips = [(1, 0, 50, [lt(0), lt(1000), lt(2120)]), (2, 60, 123, [lt(2500)])]
    before = copy.deepcopy(clips)
    first = place_markers(clips)
    assert place_markers(clips) == first
    assert clips == before
