# Pack contract

**Status: The layout part of the reopened text (the `audio/` folder, checks 2 and 4, the manifest `file` column) is implemented in WS22 (offline). The `resolve_timeline.otio` file and its scene markers are implemented in WS23 (offline). The line markers, check 4a, the "Line timings (read-only input)" reading rules and every `NOTE` line are implemented in WS25 (offline); the Resolve questions listed under "Markers" were settled in WS26 on 2026-10-09, except those the Markers section lists as still unmeasured. Approved 2026-10-03 by the owner; reopened 2026-10-07 for the `audio/` layout and `--editor resolve`, approved 2026-10-07 by the owner.**

This contract defines the `scenevoice pack` command: its CLI surface, plan-input checks, the manifest columns and CSV dialect, the pack folder layout, the Resolve timeline (the product, requested with `--editor resolve`), where the files are written, the check order, failure semantics and exit codes. It builds on the [synth contract](synth-contract.md), which owns the `NNN.wav` files and their format, the [plan contract](plan-contract.md), which owns the plan shape, and the [creator script contract](script-contract.md), which owns the source format, and relates to [`docs/specs/align-contract.md`](align-contract.md), whose output `pack` reads for line markers. It does not edit or contradict any of these, and it does not authorize implementation, workspace creation, provider calls, or a pilot (Phase1-M5-WS13 is spec only).

The Resolve timeline is the product; `scene_manifest.csv` is its fallback for editors the timeline does not cover, and `pack` still writes it on every run. `pack` works from the plan and the directory alone. It never reads the creator script, never rewrites creator text, reads no environment values (no `.env`, no key), makes no provider call and never calls `align`.

## Command surface

```
scenevoice pack [--editor resolve] [PLAN] DIR
```

- `DIR` is required: the pack folder. It holds the `audio/NNN.wav` files that `synth` wrote for the plan. It must already exist, and so must `DIR/audio`; `pack` never creates either.
- `PLAN` is optional. When omitted, the plan is read from stdin. If stdin is a terminal and no path is given, `pack` fails (exit 1, before any other I/O) instead of waiting for input, as in "Pre-flight" of the synth contract.
- A single positional argument is always `DIR`, never `PLAN`. Two positionals are `PLAN` then `DIR`.
- `--editor` is optional and takes exactly one value from a closed set that has one member today: `resolve`. The match is exact and case-sensitive (`Resolve` is not `resolve`). A missing value after the option, an empty value or any other value is a usage error: exit 2, before any I/O, with a message that names `resolve`. A repeated `--editor` follows argparse: the last one wins. Without `--editor`, `pack` writes only the manifest.
- A missing `DIR`, a third positional, or any unrecognised option is a usage error, exit 2, before any I/O.

## Pack folder layout

The pack folder is `DIR`. It holds:

```
DIR/
  audio/
    001.wav
    002.wav
    ...
  scene_manifest.csv
  resolve_timeline.otio    (only in an editor run)
  line_timings.json        (input from align; read only with --editor resolve)
```

`audio/NNN.wav` are written by `synth`; `scene_manifest.csv` and `resolve_timeline.otio` are written by `pack`. `line_timings.json` is an input written by `align`, never by `pack`. A flat `DIR/NNN.wav` left by an older run is ignored like any stray file, and development-phase packs are not migrated.

## Plan-input checks

The plan check is the one defined in "Plan-input checks" of [synth-contract.md](synth-contract.md): reading, document, shape and field rules apply unchanged, so a later edit to that section applies to `pack` too. Two points differ, both deliberately:

- The 999-scene limit (stated under "Provider request text" of the synth contract) is applied, because file names carry three digits in `audio/NNN.wav`. The 8,000-byte Gemini body limit (stated under "Gemini (Vertex) request and response" of the synth contract; ElevenLabs has per-model character limits in its own section) is not applied: `pack` never sends a body.
- `pack` also rejects a `title` that cannot be encoded as UTF-8 (for example one holding the escaped unpaired surrogate `\ud800`), because it writes the title to the CSV. This is a plan-check failure in check 1 below: FAIL prefix, exit 1, nothing written. `synth` exempts `title` because it never sends it; `pack` cannot.

## Columns

The header row is `scene,label,file,duration_s`, matching `SPEC.md`. One row per scene follows, in plan order.

- `scene`: the plan `ordinal`, as a plain decimal integer with no padding.
- `label`: the plan `title` verbatim, as carried by the plan. `pack` does not trim, strip, interpret or rewrite it. An empty `title` gives an empty label (an empty field). A `Scene N:` text inside the title is part of it and stays in the label.
- `file`: `audio/NNN.wav`, the ordinal zero-padded to 3 digits, with a forward slash and the directory part `audio/`. It is relative to the pack folder, which is `DIR`.
- `duration_s`: the clip length in seconds, with exactly 3 decimals and `.` as the separator, no thousands separator. The length is the data frame count from the WAV header divided by 24000. The division is exact (not floating point) and the result is rounded to 3 decimals with ties rounding up. A frame count of 12 is exactly 0.0005 s and is written `0.001`. The frame count is the one validated in check 4, so the clip length equals the header frame count.

## CSV dialect

- Encoding is UTF-8 with no BOM. Non-ASCII text is written as itself.
- The field separator is a comma. Quoting follows RFC 4180: a field containing a comma, a double quote, LF or CR is wrapped in double quotes, and each double quote inside it is doubled. Any other field is written bare. An empty field is written bare. An LF or CR inside a quoted field is written as is, never translated.
- Line endings are LF, one per row. This deliberately differs from RFC 4180's CRLF.
- Every row, including the last, ends with LF, so the file has a trailing newline.

## Location and extras

`pack` writes `DIR/scene_manifest.csv`, in place. It copies and moves no WAV. Files in `DIR` and in `DIR/audio` that the plan does not mention (other files, a flat `DIR/NNN.wav` from an older run, or a stale `audio/007.wav` from a longer plan) are ignored: they are not an error and are not listed in the manifest. `DIR/synth_record.json`, written by `synth`, is an ignored extra like any other unmentioned file in `DIR`: it is not a deliverable, and `pack` never reads, lists or requires it. With `--editor`, `pack` also writes a timeline file in `DIR` (stated in "Editor timeline (`--editor resolve`)" below).

`pack` without `--editor` writes only `scene_manifest.csv`, offline, with the columns of "Columns" and the dialect of "CSV dialect" above. The layout change affects only the `file` values.

A collision is any existing path (file, directory or symlink) at `DIR/scene_manifest.csv` (check 3) or, in an editor run, at `DIR/resolve_timeline.otio` (check 3a). `pack` refuses it at check time so no path that exists at that moment is overwritten. A file created after the check and before the rename is not guarded against (see Deferred).

## Editor timeline (`--editor resolve`)

This section is reopened text, approved 2026-10-07; the file and scene markers are implemented (WS23) and the line markers, check 4a and the NOTEs are implemented (WS25). With `--editor resolve`, `pack` writes one more file, `DIR/resolve_timeline.otio`, an OpenTimelineIO timeline that DaVinci Resolve imports in one step with the clips, the pauses and the markers already placed. The file is hand-written JSON; no OpenTimelineIO library is used. The name carries the editor, so a later editor's file cannot collide with it.

**File, links and collision**

- The file is `DIR/resolve_timeline.otio`, loose in `DIR`, not zipped. Every `target_url` is relative to the file's folder and has the form `audio/NNN.wav` (forward slash, ordinal zero-padded to 3 digits), the same value as the manifest `file` column. The assumption is that Resolve resolves the relative path against the `.otio` file's folder.
- The file is written under a temporary name in `DIR`, then renamed. The temporary name never ends in `.otio`.
- A collision is any existing path at `DIR/resolve_timeline.otio` (file, directory or symlink). It is refused before the write, and the message names `resolve_timeline.otio`.
- The editor run does not change the manifest rules: `scene_manifest.csv` is still written with the same columns and dialect, and a manifest collision still refuses the run first.
- The same plan, WAVs and timings give the same bytes.

**Constants**

- The frame rate is 24 frames per second (24 fps). The timeline starts at 00:00:00:00 (`global_start_time` is 0).
- There is one audio track, named `Narration`. Between consecutive clips there is a pause of 10 frames; there is none after the last clip.
- A clip's length in frames is the WAV data frame count (at 24000 Hz) divided by 1000, with the fraction dropped. This is exact integer arithmetic with no floating point: 24 frames per second over 24000 sample frames per second is one timeline frame per 1000 sample frames. The loss is under one frame per clip.
- A scene whose WAV has fewer than 1000 frames would floor to a zero-length clip, which cannot carry a marker. That is a failure of the editor run in check 4: exit 1, nothing written, and the message names the scene and the file.
- A clip's `source_range` starts at 0 and lasts the floored frame count, at rate 24. Its `available_range` starts at 0 and lasts the full WAV frame count, at rate 24000.
- Names: the timeline is `SceneVoice`, a clip is `Scene N` (N is the plan ordinal), the track is `Narration`, the stack is `tracks`. A pause is a gap with an empty name. The media reference name is empty.

**Markers**

- All markers sit on the stack, not on the track or the clips. Each is one frame long (`marked_range` has a duration of 1 frame at rate 24). A marker's start is an integer frame on the timeline, not an offset inside its clip.
- Scene marker: colour `BLUE`, at the clip's start frame. Its `name` is `Scene N: ` followed by the plan `title` verbatim. An empty title gives `Scene N` exactly (no colon, no trailing space), while the manifest keeps an empty label. Its `comment` is the plan `body` verbatim.
- Line marker: colour `GREEN`. Its `name` is `L<scene>.<n>: ` followed by the sentence text, and its `comment` is the sentence text. `<scene>` is the ordinal and `<n>` is the 1-based position of the line in that scene's entry in `line_timings.json`; a line without a start time makes no marker but still counts toward `<n>`. The sentences and start times come only from that file; its read and freshness rules are in "Line timings (read-only input)" below, and the checks that apply them are 4a in "Check order".
- A line marker's wanted frame is the clip's start frame plus the integer quotient of (start in milliseconds times 24, plus 500) divided by 1000. That is the start in frames, rounded to nearest with halves going up (a half cannot actually occur). The wanted frame is clamped to the clip's last frame, which is the clip's start frame plus its frames minus 1.
- At most one marker sits on a frame. Markers are processed in order of wanted frame, then scene marker before line markers, then creation order (scenes in plan order, lines in file order). A marker whose wanted frame is already taken moves to the next free frame within its clip. The search only goes forward: a marker never moves earlier, and a marker clamped to the clip's last frame is skipped if that frame is taken. A marker with no free frame at or after its wanted frame is skipped, with a stderr note that names the scene and the line. A scene marker is processed first at its clip's start frame, so it never moves.
- Markers are written in ascending order of their final frame.
- Confirmed in WS26 (2026-10-09, owner, Resolve 21.1.1, real packs R2 and R1): green line markers render, the `comment` text shows, and markers sit in the right places. The 2026-10-07 relocation check (a zipped pack unzipped into a folder whose name had a space, then imported) linked all clips with no import prompt or error noticed by the owner; in WS26 a zipped R2 pack unzipped under a spaced non-ASCII path imported with 5 clips linked, 5 blue and 25 green markers, and R1 imported in place. Still unmeasured: any text length limit on marker names and comments, the Finder Compress variant of the zip, relocation of R1, and how coincident markers behave (untested, avoided by construction).

**Byte facts**

The file is what Python's `json.dumps` with `indent=2` and `ensure_ascii=True` produces for the structure below, plus one final LF:

- UTF-8, 2-space indent, a newline after each opening bracket. The item separator is a bare `,` at the end of a line, never `, `. The key separator is `: `. An empty array is `[]` and an empty object is `{}`.
- In strings, LF, CR, TAB, backspace, form feed, double quote and backslash are written as `\n`, `\r`, `\t`, `\b`, `\f`, `\"` and `\\`. Every other control character, 0x7f and every non-ASCII character is written as lowercase `\uXXXX`, with a surrogate pair of two escapes above U+FFFF. So the file holds no raw non-ASCII byte. `/` is not escaped.
- Exactly one LF follows the final closing brace.
- Every `rate` and `value` is a JSON integer, with no decimal point.
- Object keys are in this fixed order, and every object carries all of its keys:
  - `Timeline.1`: `OTIO_SCHEMA`, `metadata`, `name`, `global_start_time`, `tracks`. Its `global_start_time` is a `RationalTime.1` of value 0 at rate 24, and `tracks` is the stack.
  - `Stack.1`: `OTIO_SCHEMA`, `metadata`, `name`, `source_range` (null), `effects`, `markers`, `enabled`, `children`. Its `enabled` is true, as for `Track.1`. Its `markers` hold all the markers, and its only child is the track.
  - `Track.1`: `OTIO_SCHEMA`, `metadata`, `name`, `source_range` (null), `effects`, `markers`, `enabled`, `children`, `kind`. `kind` is `Audio`, `enabled` is true, and `markers` is empty. Its children are a clip for each scene in plan order, with a gap between consecutive clips.
  - `Clip.1`: `OTIO_SCHEMA`, `metadata`, `name`, `source_range`, `effects`, `markers` (empty), `media_reference`.
  - `ExternalReference.1`: `OTIO_SCHEMA`, `metadata`, `name` (empty), `available_range`, `target_url`.
  - `Gap.1`: `OTIO_SCHEMA`, `metadata`, `name` (empty), `source_range` (start 0, 10 frames at rate 24), `effects`, `markers`.
  - `Marker.2`: `OTIO_SCHEMA`, `metadata`, `name`, `color`, `comment`, `marked_range`.
  - `TimeRange.1`: `OTIO_SCHEMA`, `duration`, `start_time`.
  - `RationalTime.1`: `OTIO_SCHEMA`, `rate`, `value`.
- Every `metadata` is `{}` and every `effects` is `[]`.

## Line timings (read-only input)

This section is implemented in WS25 (check 4a and the NOTEs included). `DIR/line_timings.json` is the only source of line markers. `pack` reads it only with `--editor resolve`, and only when it is present; `pack` without `--editor` never reads it, so a stale or malformed file is then ignored and not noted. `pack` writes no part of it and never calls `align`. This section states only what `pack` reads: the full schema is in `docs/specs/align-contract.md`, which conforms to this lower bound.

**Document and shape**

- The file is a JSON document under the same document rules as the plan check: UTF-8, no BOM, no trailing data, no duplicate keys and no `NaN`. It is an object with a `scenes` array. Any departure from this shape is malformed (rule (b)): a top level that is not an object, a missing `scenes` key or one that is not an array, and an entry or a line that is not an object. An empty `scenes` array is well-formed: every plan scene then has no entry, so it gets the missing note and a scene marker only, exit 0. An empty `lines` array is also allowed.
- Each entry of `scenes` carries `ordinal`, a JSON integer (a boolean, a float or any other non-integer number is not one); `sha256`, exactly 64 lowercase hexadecimal characters, the SHA-256 of the bytes of that scene's `audio/NNN.wav`; and `lines`, an array of objects, each with `text`, a string, and `start_ms`, a non-negative JSON integer or null (a boolean, a float, a non-integer number or a negative number is malformed).
- Unknown extra fields at any level are ignored. A null `start_ms` means no marker for that line, while its position still counts toward `<n>`.

**Rules**

- (a) File absent (nothing at that path; a dangling symlink is not absent, see (b)): scene markers only, one `NOTE` on stderr naming `line_timings.json` and saying there is no timings file, exit 0.
- (b) File present but not a regular file (a directory or a symlink, including a dangling symlink), unreadable, not valid JSON under the document rules, or malformed: an operational failure, exit 1, nothing written, found in check 4a before any write. Malformed means any entry, including an entry for a scene that is not in the plan, that is missing a required field or has one of the wrong type (an `ordinal` or `start_ms` that is not a JSON integer, or a `start_ms` below 0; null stays allowed for `start_ms`); an `ordinal` repeated in two entries; a `sha256` that is not exactly 64 lowercase hexadecimal characters; or a `text` that cannot be encoded as UTF-8 (for example an escaped lone surrogate), as for the plan's title and body.
- (c) A well-formed entry whose ordinal is not in the plan is ignored. A plan scene that has no entry, or whose recorded `sha256` differs from the SHA-256 of its current `audio/NNN.wav`, gets its scene marker only, plus one `NOTE` naming the scene and saying it is stale or missing, exit 0. This stale or missing note applies whatever the entry's `lines` hold: a stale scene whose entry has empty `lines` still gets it. Only a fresh entry (matching hash) with no lines gives no note.
- (d) `pack` never places a line marker from timings it cannot show belong to the current clip: no line marker is placed for a scene unless its entry exists and its hash matches. These rules never relax that gate.

**After `synth --scene N`.** Delete `scene_manifest.csv` and `resolve_timeline.otio` if present, then re-run `pack` (durations and positions change, so re-packing is required). Before `pack --editor resolve`, also re-run `align` (its contract is `docs/specs/align-contract.md`); a plain `pack` ignores the timings file, and in an editor run a stale scene gets a `NOTE`. Then manually re-archive any delivery zip and verify it contains the regenerated WAV and the new manifest (and the new timeline, if one is produced). A delivery zip is an operator artifact outside the tool. This is not enforced in code.

## Check order

All of these happen in this order. Nothing is written until all checks pass. Checks 3a and 4a run only with `--editor resolve`; the others run in every run. The numbers 1 to 5 are stable, and the new checks are 3a and 4a. The `--editor` value is checked at parse time, before check 1 (usage error, exit 2, as in "Command surface").

1. Read and check the plan (every run). If no `PLAN` is given and stdin is a terminal, fail first (exit 1, before any other I/O). Then read the plan and check it, in this order inside check 1: the document, shape and field rules; then the 999-scene count; then the title UTF-8 rule.
2. Check `DIR` and `DIR/audio` (every run): a `DIR` that does not exist, or that exists as a non-directory, fails. `DIR/audio` must be a real directory: a missing path, a non-directory or a symlink (even one pointing at a directory) fails, and the message names `audio`: `DIR/audio: directory does not exist` for a missing path, `DIR/audio: not a directory` for a non-directory or a symlink. `DIR` itself keeps its own check (a symlink to a directory is accepted).
3. Check the collision at `DIR/scene_manifest.csv` (every run); the message names that file.
3a. Editor only: check the collision at `DIR/resolve_timeline.otio`, a cheap path check before any WAV is read. Any existing path (file, directory or symlink) is refused, and the message names `resolve_timeline.otio`.
4. For each scene in plan order, check `DIR/audio/NNN.wav` (every run): it must be a regular file (a missing path, a directory or a symlink is rejected as not a regular file), and it must be a valid WAV under the header conditions of "Response acceptance" in "Gemini (Vertex) request and response" of the synth contract (the ElevenLabs path wraps its PCM and passes the same header validation): 24000 Hz, 1 channel, 16-bit samples, a non-empty data section, and the frame bytes present equal to the declared frame count times the frame width. The media-type condition does not apply. A `NNN.wav` that cannot be read or parsed as a WAV is invalid under this check. In an editor run, a WAV with fewer than 1000 frames also fails here (the zero-frame rule of "Editor timeline (`--editor resolve`)"). The first failing scene stops the checks. The message names the scene and the file.
4a. Editor only: read and check `DIR/line_timings.json` under "Line timings (read-only input)", which needs the WAV bytes that check 4 validated. Work out each plan scene's freshness, place the line markers under the marker rules of "Editor timeline (`--editor resolve`)", and note each skipped marker (a marker with no free frame, a `NOTE` naming the scene and the line). A malformed or unreadable file fails here, before anything is written. A missing timings file, a stale scene and a skipped marker are notes, never failures.
5. Write (every run). Without `--editor`, write the manifest under a temporary name in `DIR`, then rename it to `scene_manifest.csv`. The temporary name never ends in `.csv`. On a failed write the temporary file is removed on a best-effort basis. With `--editor resolve`, write both complete files first, each under a temporary name in `DIR` (a name never ending in `.csv` or `.otio`), then rename the manifest to `scene_manifest.csv`, then the timeline to `resolve_timeline.otio`. If the second rename fails, the manifest that this run created is removed and the temporary files are removed, on a best-effort basis, so that no new file remains. More generally, for an editor run, a failure after the temporary files start being written (writing either temporary file, or the first rename) removes whatever new files this run created (the temporary files and, if it was renamed, the manifest), on a best-effort basis. A file that existed at the collision check is not touched by this cleanup; a file created after the check and before the rename is not guarded against.

A failure at checks 1 to 4a is a failure before anything is written. A failure at check 5 (write or rename) is an operational failure, exit 1. In every failure no new manifest and no new timeline is created (best effort for the cleanup in check 5); any existing manifest or timeline remains unchanged. An existing manifest or timeline is refused at check time (checks 3 and 3a), but a rename can silently overwrite a file created between the collision check and the rename; that gap is not guarded against.

## Streams and exit codes

- stdout is always empty.
- Progress and the final OK or FAIL line go to stderr, as `scenevoice pack: ...`. Success is `scenevoice pack: OK ...`. Each failure is `scenevoice pack: FAIL ...`, the same prefix style as `scenevoice synth: FAIL ...`.
- In an editor run, stderr also carries `scenevoice pack: NOTE ...` lines before the OK line, for a missing timings file, a stale scene, a scene with no entry, and a skipped marker. They are collected during check 4a and emitted together, before check 5, in plan scene order and then line order (not in the order markers are processed), so stderr is deterministic. They are still printed if check 5 then fails: the FAIL line follows them and the exit code is 1. A `NOTE` is not a FAIL, and it never changes the exit code. Without `--editor` there are no `NOTE` lines.
- The OK line of an editor run is `scenevoice pack: OK N scenes written to DIR/scene_manifest.csv and DIR/resolve_timeline.otio`, naming both files.
- A FAIL line names the scene and file for a WAV failure, the colliding file for a collision (`scene_manifest.csv` or `resolve_timeline.otio`), `audio` for a failed `DIR/audio` check (`DIR/audio: directory does not exist` or `DIR/audio: not a directory`, with `DIR` as given), and `line_timings.json` for a timings failure.
- Tests assert only the `scenevoice pack: OK`, `scenevoice pack: NOTE` or `scenevoice pack: FAIL` prefix plus the names: for a WAV failure, the scene number and file name; for a collision failure, the file name (`scene_manifest.csv` or `resolve_timeline.otio`); for the `DIR/audio` failure, `audio`; for a timings failure, `line_timings.json`; for an editor OK line, both file names; for the missing-file `NOTE`, `line_timings.json` (no scene); for a stale or missing-scene `NOTE`, the scene; for a skipped-marker `NOTE`, the scene and the line. They do not assert the rest of the message wording.
- exit 0 on success, with or without `NOTE` lines.
- exit 1 on any operational failure: plan, limits, `DIR`, `DIR/audio`, collision (manifest or timeline), WAV (including the zero-frame rule), a malformed or unreadable `line_timings.json`, filesystem, including a terminal stdin with no `PLAN`.
- exit 2 for usage errors: a missing `DIR`, extra positionals, an unrecognised option, or a bad `--editor` (a missing value, an empty value or any value but `resolve`). Usage errors happen before any I/O.

## Worked examples

Two-scene plan whose titles hold a comma, a double quote and non-ASCII text. Scene 1 is `Café, au lait` with a 50400-frame clip (50400 / 24000 = 2.1). Scene 2 is `The "big" day` with a 123456-frame clip (123456 / 24000 = 5.144). The written `scene_manifest.csv`:

```
scene,label,file,duration_s
1,"Café, au lait",audio/001.wav,2.100
2,"The ""big"" day",audio/002.wav,5.144
```

The file ends with LF after the last row.

Empty title (scene 1, 50400 frames): the label is an empty field.

```
1,,audio/001.wav,2.100
```

Title containing CR (scene 1, `a`, CR, `b`, with 36000 frames, 36000 / 24000 = 1.5): the field is quoted and the CR is kept. The row is these bytes, hex: `31 2c 22 61 0d 62 22 2c 61 75 64 69 6f 2f 30 30 31 2e 77 61 76 2c 31 2e 35 30 30 0a`.

Ties: 12 frames is 0.0005 s and is written `0.001`; 36 frames is 0.0015 s and is written `0.002`. A clip of 36000 frames is 1.5 s and is written `1.500`.

Stdin run: the `plan` output piped to `pack`, with `out` holding `audio/001.wav` and `audio/002.wav` for a two-scene plan.

```
scenevoice plan sample/scripts/short.md | scenevoice pack out
```

stdout is empty and stderr ends with a line of the form `scenevoice pack: OK 2 scenes written to out/scene_manifest.csv`, and the exit status is 0.

Failure: `out` holds `audio/001.wav` but no `audio/002.wav` for a two-scene plan.

```
scenevoice pack: FAIL scene 2: audio/002.wav is missing or not a regular file
```

The exit status is 1, stdout is empty, and no new manifest is created; any existing manifest remains unchanged.

### Editor run (`--editor resolve`)

These examples are data and prose. The wording of a `NOTE` beyond the names it carries is illustrative; tests assert only the prefix and the names (see "Streams and exit codes").

Layout of the pack folder after an editor run for the two-scene plan above (the `align` output `line_timings.json` was placed there beforehand):

```
out/
  audio/
    001.wav
    002.wav
  scene_manifest.csv
  resolve_timeline.otio
  line_timings.json
```

The manifest rows are the ones above (`audio/001.wav` and `audio/002.wav` in the `file` column); an editor run does not change them. The `target_url` of the two clips are the same two values.

Frame arithmetic for the same two scenes, with the pause and the clip lengths of "Editor timeline (`--editor resolve`)":

- Scene 1 has 50400 WAV frames, so its clip is 50 frames (50400 divided by 1000, fraction dropped), frames 0 to 49. The gap that follows covers frames 50 to 59 (10 frames).
- Scene 2 has 123456 WAV frames, so its clip is 123 frames (123456 divided by 1000, fraction dropped) and starts at frame 60. There is no pause after it, so the track is 60 plus 123, that is 183 frames long.
- The scene markers (blue) sit at frames 0 and 60.

Minimal timings file for those scenes (the two `sha256` values are placeholders: each is 64 lowercase hexadecimal characters, here repeated `a` and repeated `b`, standing for the SHA-256 of `audio/001.wav` and `audio/002.wav`; the file is shown unindented for brevity, which `pack` does not require):

```
{"scenes": [
  {"ordinal": 1,
   "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
   "lines": [{"text": "First sentence.", "start_ms": 0},
             {"text": "Second sentence.", "start_ms": 1000},
             {"text": "Third sentence.", "start_ms": 2120}]},
  {"ordinal": 2,
   "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
   "lines": [{"text": "Fourth sentence.", "start_ms": 2500}]}
]}
```

Line markers, when both hashes match the current WAVs (a marker's wanted frame is the clip start plus (start_ms times 24, plus 500) divided by 1000, clamped to the clip's last frame):

- Scene 1 (clip start 0, last frame 49). `L1.1`, `start_ms` 0: wants frame 0, which the scene marker holds, so it moves to frame 1. `L1.2`, 1000: (1000 times 24, plus 500) divided by 1000 is 24, so frame 24. `L1.3`, 2120: wants frame 51, past the clip, so it is clamped to frame 49.
- Scene 2 (clip start 60). `L2.1`, 2500: (2500 times 24, plus 500) divided by 1000 is 60, so frame 60 plus 60, that is 120.
- Rounding, outside this file's scenes: 1020 ms is 24.48 frames and gives 24 (rounds down); 1021 ms is 24.504 frames and gives 25 (rounds up).

Final marker frames, in ascending order: 0 (scene 1, blue), 1 (`L1.1`), 24 (`L1.2`), 49 (`L1.3`), 60 (scene 2, blue), 120 (`L2.1`). The run is a success, exit 0, with no `NOTE`, and stderr ends with:

```
scenevoice pack: OK 2 scenes written to out/scene_manifest.csv and out/resolve_timeline.otio
```

Stale scene: scene 2 was regenerated with `synth --scene 2` after the timings were made, so the recorded `sha256` of scene 2 no longer matches `audio/002.wav`. Scene 2 gets its scene marker only; scene 1 is fresh and keeps its three line markers. Stderr, exit 0:

```
scenevoice pack: NOTE scene 2: line timings stale, scene marker only
scenevoice pack: OK 2 scenes written to out/scene_manifest.csv and out/resolve_timeline.otio
```

Missing timings file: `line_timings.json` is not in `out`. Every scene gets its scene marker only, with one `NOTE` before the OK line, exit 0:

```
scenevoice pack: NOTE no line_timings.json, scene markers only
scenevoice pack: OK 2 scenes written to out/scene_manifest.csv and out/resolve_timeline.otio
```

Skipped marker: a one-scene plan whose `audio/001.wav` has 1500 sample frames. The clip is 1500 divided by 1000, fraction dropped, that is 1 frame, so its only frame (frame 0) holds the scene marker. A line at `start_ms` 0 wants frame 0, which is taken, and the clip has no later frame, so the marker is skipped and the run still succeeds (exit 0). The `NOTE` names the scene and the line:

```
scenevoice pack: NOTE scene 1 line 1: marker skipped, no free frame
scenevoice pack: OK 1 scenes written to out/scene_manifest.csv and out/resolve_timeline.otio
```

A WAV of 999 frames would floor to zero frames and fail check 4 instead (exit 1, nothing written).

## Deferred

- `pack --out` to a separate folder, with copied WAVs.
- Failing on extra files or extra WAVs in `DIR` or `DIR/audio`.
- Overwrite or merge of an existing manifest.
- A manifest or timeline created between the collision check and the write is not guarded against, and neither is a file created between the collision check and the rename step: the rename can silently overwrite it.
- Other editors (Premiere, Final Cut and others): each needs its own timeline file name and its own writer, scheduled only on a real request.
- The `.otioz` fallback: WS26's relocated import passed (2026-10-09), so it was not needed; reopen it if a real prospect's import fails.
- Marker text length limits.
- Reporting every bad scene in one message.
- Other columns, formats or an audio check beyond the header.
