# Creator script contract

This contract freezes the source format for a SceneVoice creator script. `SPEC.md` is the product boundary and `docs/architecture.md` the responsibility boundary. It does not authorize implementation, workspace creation, provider calls, or a pilot.

In Stage A every creator script given to the SceneVoice CLI (`scenevoice plan`) must follow this contract. `sample/scripts/short.md` and `sample/scripts/long.md` are reference examples of the format.

## Source

A valid source is UTF-8 text containing one or more scenes. Each scene has a one-based ordinal, a title, and a body. Zero padding and file-name binding are not defined here.

Creator scripts conventionally look like this. Only the `## ` scene markers are defined by this contract; everything else before the first marker is preamble:

```
# Video title

[Pronunciations]
Word = phonetic-spelling

## Scene 1: Title
Spoken text.

## Scene 2: Title
Spoken text.
```

## Lexical rules

- Input must be valid UTF-8 without an initial BOM. Invalid UTF-8, a BOM, CR (`U+000D`), and controls other than LF (`U+000A`) are invalid.
- LF is the only line terminator. Scene text is not rewritten.
- A scene marker starts at column one with exactly `##`, then exactly one ASCII space, and ends with LF or EOF. No Markdown, indentation, or fence parsing applies.
- A title is every code point after the marker delimiter and before its LF. It may repeat and needs at least one code point outside Unicode White_Space.
- A body starts after its marker LF and ends immediately before the next marker or EOF. It needs at least one code point outside Unicode White_Space.
- Text before the first valid marker is free preamble and is ignored. A valid document must contain a marker; empty or preamble-only input is invalid.
- A `[Pronunciations]` block, when present, is preamble. It is ignored: not parsed, not spoken, and no pronunciation behavior is defined.
- The `Scene N:` text in a title is not interpreted. The ordinal comes from position only, so gaps or repeats in `N` are valid.

## Spoken text

Every retained body character is spoken text. There is no comment or direction syntax, so bracketed notes and direction-like prose are spoken literally. Authors must not put comments or directions in the script.

## Rejection

Reject input with invalid UTF-8, a BOM, CR, a disallowed control character, no marker, a blank title, or an empty or White_Space-only body.
## Examples

- Preamble is ignored until the first valid column-one marker.
- `## Arrival` followed by LF has title `Arrival`; `##   Arrival` has a title beginning with two extra spaces. Repeated titles are valid and get successive ordinals.
- A final valid marker followed by LF and EOF, or directly by EOF, has an empty body and is rejected.
- A `[Pronunciations]` block with `Aurelius = Oh-REE-lee-us` lines before the first marker is ignored.
- In `sample/scripts/long.md`, `Scene 6: …` follows `Scene 4: …` and gets ordinal 5; the number in the title is not interpreted.
- `[pause]`, `whisper this`, and `say this slowly` in a body are spoken literally.
