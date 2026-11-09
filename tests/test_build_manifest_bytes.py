from scenevoice.pack import build_manifest
from scenevoice.synth import PlanScene

HEADER = b"scene,label,file,duration_s\n"


def scene(ordinal, title):
    return PlanScene(ordinal=ordinal, title=title, body="x")


def test_contract_two_row_example():
    scenes = [scene(1, "Café, au lait"), scene(2, 'The "big" day')]
    expected = (
        b"scene,label,file,duration_s\n"
        b'1,"Caf\xc3\xa9, au lait",audio/001.wav,2.100\n'
        b'2,"The ""big"" day",audio/002.wav,5.144\n'
    )
    assert build_manifest(scenes, [50400, 123456]) == expected


def test_cr_title_row_matches_contract_hex():
    row = bytes.fromhex("312c22610d62222c617564696f2f3030312e7761762c312e3530300a")
    assert build_manifest([scene(1, "a\rb")], [36000]) == HEADER + row


def test_lf_title_is_quoted_with_lf_kept():
    assert build_manifest([scene(1, "a\nb")], [36000]) == HEADER + b'1,"a\nb",audio/001.wav,1.500\n'


def test_crlf_title_keeps_cr_lf_inside_quotes_only():
    out = build_manifest([scene(1, "a\r\nb")], [36000])
    assert out == HEADER + b'1,"a\r\nb",audio/001.wav,1.500\n'


def test_empty_title_is_bare():
    assert build_manifest([scene(1, "")], [50400]) == HEADER + b"1,,audio/001.wav,2.100\n"


def test_title_of_only_a_double_quote():
    assert build_manifest([scene(1, '"')], [50400]) == HEADER + b'1,"""",audio/001.wav,2.100\n'


def test_scene_prefix_kept_verbatim():
    out = build_manifest([scene(3, "Scene 3: Intro")], [24000])
    assert out == HEADER + b"3,Scene 3: Intro,audio/003.wav,1.000\n"


def test_leading_and_trailing_spaces_kept():
    out = build_manifest([scene(1, "  pad  ")], [24000])
    assert out == HEADER + b"1,  pad  ,audio/001.wav,1.000\n"


def test_no_bom_and_ends_with_lf():
    out = build_manifest([scene(1, "t")], [24000])
    assert not out.startswith(b"\xef\xbb\xbf")
    assert out.startswith(b"scene,")
    assert out.endswith(b"\n")
    assert b"\r" not in out


def test_ordinal_seven_is_unpadded_scene_and_padded_file():
    out = build_manifest([scene(7, "t")], [24000])
    assert out == HEADER + b"7,t,audio/007.wav,1.000\n"


def test_rows_follow_plan_order():
    out = build_manifest([scene(1, "a"), scene(2, "b")], [24000, 48000])
    assert out == HEADER + b"1,a,audio/001.wav,1.000\n2,b,audio/002.wav,2.000\n"
