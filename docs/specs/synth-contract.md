# Synth contract

**Status: The 2026-10-27 reopening (Milestone 9, WS31) under which `align` reads `DIR/synth_record.json` and each script is voiced by one provider (the sentences in Synth record, Single-scene regeneration D10 and the worked record example) was approved by the owner on 2026-10-27 and built in WS32 on the `align` side (no change to `synth`; offline, fixture-tested), then accepted on 2026-10-27 on a copy of the WS30 R2 pack with no provider call: `align` took all 5 scenes from the record with no key and zero calls, and the owner's Resolve import and ear check passed. Earlier history: The 2026-10-26 reopening for ElevenLabs and the synth record file (`DIR/synth_record.json`) was approved 2026-10-26 by the owner. WS28 implemented the provider seam, `DIR/synth_record.json` for Gemini scenes and the `--scene` settings check; WS29 implemented the ElevenLabs path (the four models, the post-parse voice check, the ElevenLabs request, response, clamp and record entries, and the `--scene` check for ElevenLabs entries) and added the owner-approved rule that a `--voice` or `--language` value that cannot be encoded as UTF-8 is an operational failure (Command surface). Both were offline and fixture-tested with no hosted call; WS30 then live-accepted the ElevenLabs path on `eleven_flash_v2_5` on 2026-10-26 (9 ElevenLabs calls and 814 Free-tier credits against a ceiling of 15 and 2,000: the error table for a bad key, a made-up voice ID and a library voice; a five-scene run with the alignment kept; `--scene 2` regeneration and the settings-mismatch refusal; `align` and `pack --editor resolve` on the result, imported into Resolve 21.1.1 by the owner) and proved the Vertex seam with one call on `gemini-3.8-flash-lite-tts`. Earlier: the audio layout reopening of 2026-10-07 (WAVs under `DIR/audio/`) was approved 2026-10-07 by the owner and implemented in WS22 (offline, fixture-tested; no hosted call). Before WS22 the code wrote `DIR/NNN.wav`.** Earlier status: **reopened 2026-10-06 for single-scene regeneration (`--scene N`); approved 2026-10-06 by the owner and implemented in WS20 (offline, fixture-tested; live-accepted on 2026-10-06 for one scene on `gemini-3.8-flash-lite-tts`, Algenib).** Earlier history: reopened 2026-10-05 for the 30 prebuilt voices and the required `--model`, approved 2026-10-05 by the owner and implemented in WS18 (offline, fixture-tested; the new voices and `gemini-3.8-flash-lite-tts` are not ear-verified); reopened 2026-10-03 for the 3.8 bump, request side owner-approved; response side rewritten in WS12 and owner-approved 2026-10-03; originally approved 2026-10-02 by the owner for gemini-3.1-flash-tts. The request side (CLI defaults, provider request text and style, model and request shape, byte limit) was approved in the 2026-10-03 reopening. The response side (audio media type acceptance, header validation, response handling, audio limit) was rewritten in WS12 for the 3.8 `audio/wav` shape. The location paragraph records the outcome of WS12's first live call on `global`.

Implementer note: the WS27 reopening itself did not change `README.md` or `.env.example`. WS28 left both unchanged; WS29 added `ELEVENLABS_API_KEY` to `.env.example` and left the README unchanged (its Gemini example and its links stay valid).

This contract defines the `scenevoice synth` command: its CLI surface, plan-input checks, provider request text and style, output files, failure semantics and exit codes. It builds on the [plan contract](plan-contract.md), which owns the plan shape, and the [creator script contract](script-contract.md), which owns the source format. It does not edit or contradict either, and it does not authorize implementation, workspace creation, provider calls, or a pilot.

`synth` works from the plan alone, except that `--scene` also reads `DIR/synth_record.json` (see Synth record). It never reads the creator script and never rewrites creator text.

## Command surface

```
scenevoice synth [PLAN] --out DIR --voice VOICE --model {gemini-3.8-flash-tts|gemini-3.8-flash-lite-tts|eleven_flash_v2_5|eleven_v4} [--language LANG] [--instruction TEXT] [--scene N]
```

- `PLAN` is optional. When omitted, the plan is read from stdin. If stdin is a terminal and no path is given, `synth` fails (exit 1, before any other I/O) instead of waiting for input.
- `--out DIR` is required. The WAVs are written to `DIR/audio/NNN.wav`; a full run creates `DIR/audio/`. Creation timing, and the rule that `--scene` creates nothing and requires `DIR/audio` to exist, are defined in Pre-flight.
- `--model` is required and has no default. It accepts exactly four values, as an exact match: no trimming, no case folding. `gemini-3.8-flash-tts` and `gemini-3.8-flash-lite-tts` select Vertex Gemini. `eleven_flash_v2_5` and `eleven_v4` select ElevenLabs. Any other value, including `eleven_v3` and `eleven_multilingual_v2`, is a usage error, exit 2, offline, and the message names all four models. An empty or repeated `--model=` is left to argparse (an invalid choice, or the last occurrence wins).
- The provider is inferred from `--model`. There is no `--provider` option and no default model. The four model values are disjoint, so no second option is needed.
- `--voice` is required and has no default. Its rule depends on the provider:
  - With a Gemini model it accepts only one of the 30 prebuilt voice names below, as an exact, case-sensitive match: no trimming, no case folding. Any other value is a usage error and fails offline. The names, alphabetically: Achernar, Achird, Algenib, Algieba, Alnilam, Aoede, Autonoe, Callirrhoe, Charon, Despina, Enceladus, Erinome, Fenrir, Gacrux, Iapetus, Kore, Laomedeia, Leda, Orus, Puck, Pulcherrima, Rasalgethi, Sadachbia, Sadaltager, Schedar, Sulafat, Umbriel, Vindemiatrix, Zephyr, Zubenelgenubi. This list is the oracle for tests.
  - With an ElevenLabs model it is a free-text ElevenLabs voice ID. Offline it is only checked as non-blank (blank as in the script contract), as an exact string: no trimming, no case folding, no length or character check. The provider validates the ID.
- `--language` applies to Gemini models only. When it is not passed with a Gemini model, it is `en-GB`; the default is resolved after the provider is known. It is sent to the provider as `languageCode` (see Gemini (Vertex) request and response). With an ElevenLabs model, passing `--language` at all, even `--language en-GB`, is a usage error (see the layering paragraph below).
- `--instruction` applies to Gemini models only. It is optional and has no default: there is no standing instruction text. When it is omitted, the request carries no style. When it is passed, its text is sent as the style (see Gemini (Vertex) request and response). With an ElevenLabs model, passing `--instruction` is a usage error. Accent and style come from the ElevenLabs voice.
- `--scene N` is optional. `N` is an integer (an argparse `int`) that selects one scene by ordinal and regenerates only that scene (see Single-scene regeneration). It takes no list and no range; a repeated `--scene` uses the last value. It replaces `DIR/audio/NNN.wav`, and `--out` and `DIR/audio` must already exist as directories. With `--scene`, `--voice`, `--model`, `--language` and `--instruction` are required or defaulted exactly as without it. The operator still re-passes the original settings. `synth` records the voice, model, language and instruction of each written WAV in `DIR/synth_record.json` and checks the passed settings against that record before any provider call (see Single-scene regeneration, D10).
- `--help` prints the four accepted models and the 30 Gemini voices, with the note that an ElevenLabs model takes a voice ID instead. It says that `--language` and `--instruction` apply to Gemini models only. The `--scene` help says that the settings are checked against `synth_record.json`, and no longer says the outputs lack them.

An explicitly passed `--instruction` that is empty or blank (blank as in the script contract) is a usage error, exit 2, before any I/O. An instruction that cannot be encoded as UTF-8 is an operational failure: exit 1 with the FAIL prefix.

A `--voice` or `--language` value that cannot be encoded as UTF-8 is an operational failure: exit 1 with the FAIL prefix, before any I/O (core texts `voice cannot be encoded as UTF-8` and `language cannot be encoded as UTF-8`).

Usage errors are layered. Gemini CLI exit codes and pinned messages are unchanged.

- Argparse layer. Required options, a `--model` outside the four values, a blank `--language`, a blank `--instruction` and a non-integer `--scene` are reported by argparse as parsed, in command-line order. One error is reported, exit 2, before any I/O. A missing required option is reported only if no value error came first.
- Post-parse CLI step. It runs only when argparse succeeded, in this order: voice, then `--language`, then `--instruction`. Each failure is one error, exit 2, before any I/O.
  - A Gemini model with a voice outside the 30 names: the message names the offending value and all 30 voices. The contract pins this content, not argparse's exact format.
  - An ElevenLabs model with a blank voice: `scenevoice synth: error: argument --voice: must not be blank`.
  - An ElevenLabs model with an explicit `--language`: `scenevoice synth: error: argument --language: not supported with an ElevenLabs model`.
  - An ElevenLabs model with an explicit `--instruction`: `scenevoice synth: error: argument --instruction: not supported with an ElevenLabs model`.
- Core layer (`run_synth`, for direct callers). The checks run in this order: model, voice, language, instruction. The model is checked first because the voice rule depends on the provider. The first failure wins, is reported as a `FAIL` line, and exits 1, before any I/O. The core `language` may be absent; for a Gemini model an absent language is `en-GB`. The texts:
  - Model: `model must be one of gemini-3.8-flash-tts, gemini-3.8-flash-lite-tts, eleven_flash_v2_5, eleven_v4`.
  - Voice with a Gemini model: `voice must be one of the 30 prebuilt voices (see the synth contract)`.
  - Voice with an ElevenLabs model: `voice must not be blank`.
  - Voice with an ElevenLabs model that cannot be encoded as UTF-8: `voice cannot be encoded as UTF-8`.
  - Language with an ElevenLabs model: `--language is not supported with an ElevenLabs model`.
  - Language with a Gemini model that cannot be encoded as UTF-8: `language cannot be encoded as UTF-8`.
  - Instruction with an ElevenLabs model: `--instruction is not supported with an ElevenLabs model`.
  - The blank-language and blank-instruction texts are unchanged.
  - For an ElevenLabs model, any present language or instruction, blank or not, gets the "not supported" text above (a direct `run_synth` caller; on the CLI argparse rejects blanks first).

The CLI path never reaches the core text for a value that argparse or the post-parse step already rejected. The core `FAIL` forms are preceded by `scenevoice synth: FAIL `.

## Plan-input checks

The plan check is strict and mirrors the plan contract.

- Reading: an unreadable path, a directory given as `PLAN`, or empty stdin fails with a message in the form `cannot read file (...)`, as in `scenevoice plan`.
- Document: reject input that is not UTF-8, a leading BOM, empty or whitespace-only input, invalid JSON, trailing data after the document, duplicate object keys, and `NaN` or `Infinity`.
- Shape: an object whose only key is `scenes`; a non-empty array; each scene an object with exactly `ordinal`, `title` and `body`.
- `ordinal` is a JSON integer token, consecutive from 1 in array order. `true`, `false`, `1.0` and `1e0` are rejected.
- `title` is a string. It may be empty or any text, because `synth` never sends it.
- `body` is a string that is not blank. Blank means empty or White_Space-only, as in the script contract: a body needs at least one code point outside Unicode White_Space.
- A `body` that cannot be encoded as UTF-8 (for example one holding the escaped unpaired surrogate `\ud800`, which JSON parsing accepts) is a plan-check failure, reported like any other with the FAIL prefix, exit 1, no output, no provider call and no traceback. `title` is exempt because it is never sent.

Any plan-check failure means nothing is written and no provider call is made.

## Provider request text

The `text` sent for a scene is the `body` verbatim. Nothing is prepended or joined to it, and the `title` is not sent.

Each provider has its own length limit, checked offline before the first provider call: see Gemini (Vertex) request and response for the byte limit and ElevenLabs request and response for the character limit.

More than 999 scenes is rejected, because file names carry three digits. This count check runs first, before the byte check and before the character check.

## Output

For each scene `synth` writes `DIR/audio/NNN.wav`, where NNN is the ordinal zero-padded to 3 digits. The pack folder layout is `DIR/audio/NNN.wav`, `DIR/scene_manifest.csv` and, with `pack --editor`, a per-editor timeline file (the product); `synth` writes the WAVs and also `DIR/synth_record.json` (see Synth record), and nothing else.

Each file is a 24 kHz, mono, 16-bit PCM WAV. For a Gemini model, the provider returns the file as a WAV (declared media type `audio/wav`), and `synth` writes the decoded bytes unchanged after validating the header. For a Gemini model, `synth` adds no header and does not convert audio. For an ElevenLabs model the provider returns raw PCM, and `synth` wraps it as a WAV with a standard header (see ElevenLabs request and response); the file facts above are the same. For a Gemini model, the earlier shape (base64 headerless `audio/L16` PCM wrapped by `synth`) is superseded and is no longer accepted.

A WAV appears at its final name only when complete. It is written under a temporary name in the same directory (`DIR/audio`) and then renamed, so a write error such as a full disk leaves no partial `audio/NNN.wav`. With `--scene`, a failed regeneration leaves the old `audio/NNN.wav` byte-identical. On a failed write the temporary file is removed on a best-effort basis, and a leftover temporary name never has the `.wav` suffix.

A collision is any existing path at `DIR/audio/NNN.wav` (file, directory or symlink). It is refused before any provider call. `synth` never overwrites a WAV, except for the `--scene` replacement (see Single-scene regeneration). The record path `DIR/synth_record.json` is the one other path `synth` writes: a full run replaces an existing regular file there, and a non-regular path there is refused before any provider call (see Pre-flight). Unrelated or stale files in `DIR` and in `DIR/audio` (for example an old `audio/007.wav` from a longer plan) are left alone and are not an error. This includes a flat `DIR/NNN.wav` from an older run: it is an ignored flat file, it does not collide, and `synth` neither migrates nor warns about it.

## Synth record

`synth` also writes `DIR/synth_record.json`, loose in `DIR` and outside `audio/`, so a zip of `audio/` stays clean. Both providers write it. It records the settings and the accepted alignment of each written WAV. It is not a deliverable. It is a working record that `synth --scene` reads (see Single-scene regeneration). `pack` ignores it; `align` reads it (check 5a of the [align contract](align-contract.md)), and what counts as a malformed record is defined in Single-scene regeneration, D11, and that definition also governs `align`. Each script is voiced by one provider (see `SPEC.md`), so a record holds entries of one provider, and `--scene N` uses the same provider as the rest of the pack; `synth` does not enforce this.

**Schema**

- The top level is a wrapper object with a `scenes` key and no other top-level key. `scenes` is an array in plan order (ascending ordinal).
- Each entry is an object with exactly these seven keys, in this order:
  - `ordinal`: the plan scene's ordinal, a JSON integer.
  - `sha256`: 64 lowercase hexadecimal characters, the SHA-256 of the exact bytes of the written `audio/NNN.wav`.
  - `voice`: the `--voice` value.
  - `model`: the `--model` value.
  - `language`: the language sent, a string for a Gemini model, `null` for an ElevenLabs model.
  - `instruction`: the instruction text verbatim, `null` when none was given and always `null` for an ElevenLabs model.
  - `alignment`: `null` for a Gemini model. For an ElevenLabs model, an object with exactly `characters`, `character_start_times_seconds` and `character_end_times_seconds`, the accepted arrays of equal length, after the clamp (see ElevenLabs request and response). They are the provider's `alignment`, not `normalized_alignment`.
- No other field at any level. The seed and the provider are not recorded.

**Byte facts**

The file is what Python's `json.dumps` with `indent=2` and `ensure_ascii` off produces for the structure above, encoded as UTF-8, plus one final LF. In words, so a golden fixture needs no library:

- UTF-8 with no byte order mark, 2-space indent, a newline after each opening bracket of a non-empty array or object, and nothing between the brackets of an empty one. The item separator is a bare `,` at the end of a line, never `, `. The key separator is `: `. An empty array is `[]`.
- Keys are in the fixed order above, and every object carries all of its keys: `scenes`; then the seven entry keys; then, inside `alignment`, `characters`, `character_start_times_seconds`, `character_end_times_seconds`.
- `ensure_ascii` is off, so a non-ASCII character is written as itself. String escapes are as in the align contract's timings file.
- `ordinal` is a JSON integer. Each time in the alignment is written as Python's float representation (for example `0.0` and `0.08`). `null` is written unquoted.
- The file is written as bytes with no newline translation. Exactly one LF follows the final closing brace, and the file ends with that one LF.
- The empty record is `{`, LF, two spaces, `"scenes": []`, LF, `}`, LF.

Worked example (data; the `sha256` values are stand-ins of 64 characters). Scene 1 is a Gemini entry and scene 2 is an ElevenLabs entry; the two entry shapes are shown together only for illustration. A real record holds the entries of one provider, and a record that mixes providers is unsupported (see Single-scene regeneration, D10):

```
{
  "scenes": [
    {
      "ordinal": 1,
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "voice": "Algenib",
      "model": "gemini-3.8-flash-tts",
      "language": "en-GB",
      "instruction": null,
      "alignment": null
    },
    {
      "ordinal": 2,
      "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "voice": "EXAVITQu4vr4xnSDxMaL",
      "model": "eleven_flash_v2_5",
      "language": null,
      "instruction": null,
      "alignment": {
        "characters": [
          "H",
          "i",
          "."
        ],
        "character_start_times_seconds": [
          0.0,
          0.08,
          0.16
        ],
        "character_end_times_seconds": [
          0.08,
          0.16,
          0.2
        ]
      }
    }
  ]
}
```

**Write points**

- Full run: after the writability probe and before the provider factory is built and before the first provider call, `synth` atomically writes the empty record `{"scenes": []}`. It replaces any existing regular file without reading it, so a malformed old record is overwritten the same way. A full run therefore starts fresh whatever fails later, and a later `--scene` on that directory finds no entry and takes the no-record path.
- After each scene's WAV rename, `synth` rewrites the whole record with that scene's entry added, so a stop-and-keep run leaves an entry for every kept WAV.
- `--scene N`: after the WAV rename, `synth` replaces the entry for ordinal N, or inserts it in ascending ordinal order when absent. Every other entry is carried over as parsed and re-serialised under the byte facts above. If `DIR/synth_record.json` is absent, the file is created then.
- Each write goes to a temporary file in `DIR` whose name never ends in `.json`, then an atomic rename onto `synth_record.json`. Removing the temporary file after a failure is best-effort; a leftover is harmless.
- A crash or failure between a WAV rename and the record write leaves the old entry. This is accepted.
- A failed record write (for example a full disk) is an operational failure and exits 1. In a full run it follows stop-and-keep: the generic write-failure `FAIL` line, with the WAVs already written kept. With `--scene` the new WAV, already renamed, is kept and the old entry remains. The empty-record write before the first call fails the same way, exit 1 before any call with nothing synthesized.
- A non-regular path at `DIR/synth_record.json` (a directory, a symlink including a dangling one, or any other non-regular file) is refused in pre-flight before any call, in a full run and with `--scene` (see Pre-flight).
- On `--scene`, a hand-replaced or hand-deleted WAV is handled as stated in Single-scene regeneration D10.

## Single-scene regeneration

`--scene N` regenerates one scene's WAV from the plan with one provider call and atomically replaces `DIR/audio/NNN.wav`. The rules:

- D1. `--scene N` is the only WAV overwrite path (this concerns WAVs; a full run does replace `DIR/synth_record.json`, see Synth record). A full run (no `--scene`) still refuses every WAV collision. Resume and skip-existing remain deferred.
- D2. The old take is replaced atomically, after the new WAV has passed header validation, through the temporary-name-then-rename write described under Output. The temporary file is written only after the new WAV has passed header validation, and the rename is the only step that touches the old file. There is no backup of the old take, no notice that one was replaced, and no `--replace` flag. Any failure before the rename leaves the old file byte-identical.
- D3. `--out` and `DIR/audio` must already exist as directories, and `DIR/audio` must not be a symlink (even one that points to a directory). Nothing is created, not `DIR`, not `DIR/audio` and not their parents. The writability probe still runs, on `DIR/audio`.
- D4. `N` is an argparse `int`. A non-integer token is a usage error, exit 2, before any I/O. An integer outside 1 to the plan's scene count, including 0 and negatives, is an operational failure, exit 1, reported after the plan check and naming the scene count.
- D5. The whole plan is still checked (document, shape, field rules, 999-scene count, body limit for the model, for every scene), not only the selected scene. Any plan-check failure means no provider call, as for a full run.
- D6. The target `DIR/audio/NNN.wav` may be absent or may exist as a regular file. A directory, a symlink (even one that points to a regular file) or a dangling symlink at that name is refused before any provider call. Other files in `DIR` and `DIR/audio` (including a flat `DIR/NNN.wav`) are untouched and unchecked.
- D7. Exactly one provider call is made, for the selected scene. The voice, model, language and instruction rules are unchanged, and the operator re-passes them. They are now checked against `DIR/synth_record.json` (D10).
- D8. Progress is `scene N/T written to audio/NNN.wav` (T is the plan scene count). Success is `scenevoice synth: OK scene N written to DIR/audio/NNN.wav`.
- D9. Operator step after a regeneration, not enforced in code: delete `scene_manifest.csv` and `resolve_timeline.otio` if present, then re-run `pack` (durations and positions change, so re-packing is required). Before `pack --editor resolve`, also re-run `align` (its contract is `docs/specs/align-contract.md`); a plain `pack` ignores the timings file, and in an editor run a stale scene gets a `NOTE`. Then manually re-archive any delivery zip and verify it contains the regenerated WAV and the new manifest (and the new timeline, if one is produced). A delivery zip is an operator artifact outside the tool. `synth` itself updates the record entry for the regenerated scene (see Synth record), so the operator deletes nothing for the record.
- D10. Settings check. Before any provider call, `--scene N` compares four recorded settings with the resolved passed values: voice, model, language and instruction. The comparison is exact: no trimming, no case folding, and the instruction is compared verbatim. For a Gemini model an omitted `--language` compares as `en-GB`. An ElevenLabs entry holds `null` language and instruction, and an ElevenLabs run passes none.
  - With a valid entry for ordinal N whose settings differ in any field, `synth` refuses: exit 1, no provider call, the pinned mismatch `FAIL` below. There is no override flag. To change a setting, re-synth into a new `DIR`.
  - With no `DIR/synth_record.json`, or a valid record with no entry for ordinal N, the regeneration proceeds. `synth` prints the matching `NOTE` on stderr before the call, the exit code is unchanged, and the entry is written after the WAV rename (see Synth record). A record that mixes providers is unsupported, and `synth` does not enforce one provider; the model mismatch refusal above, when an entry exists, is unchanged.
  - The `sha256` of the existing WAV is not verified. A hand-replaced or hand-deleted WAV is still checked against its entry. This is accepted.
  - The refusal runs after the environment check, so it needs credentials. This is accepted.
  - The record is not checked against the plan: an entry for an ordinal beyond the plan's scene count is kept untouched.
- D11. Malformed record. A `--scene N` run whose `DIR/synth_record.json` is malformed fails: exit 1, no provider call, the pinned malformed `FAIL` below. The operator can delete the file, which takes the no-record `NOTE` path of D10. The record is validated as a whole, not only the entry for N, because the whole file is rewritten and a bad entry would be carried forward. It is not validated against the plan. A full run never reads the record. The record is malformed when any of these holds:
  - The file cannot be read.
  - The bytes are not UTF-8, start with a byte order mark, are not exactly one JSON document, have trailing data, repeat an object key, or contain `NaN` or `Infinity` (the plan check's strict decode rules).
  - The top level is not an object whose only key is `scenes`, or `scenes` is not an array of objects that each have exactly the seven entry keys of the Synth record schema.
  - An `ordinal` is not a JSON integer of at least 1 (booleans and `1.0` are rejected), or the ordinals are not strictly ascending.
  - A `sha256` is not 64 lowercase hexadecimal characters.
  - A `voice` or `model` is not a non-blank string, or a `model` is none of the four accepted models.
  - A `language` or `instruction` is neither a string nor `null`.
  - An `alignment` is neither `null` nor an object with exactly `characters`, `character_start_times_seconds` and `character_end_times_seconds`, holding arrays of equal length whose elements are valid as the ElevenLabs response acceptance rules accept them (characters are strings, times are finite non-negative numbers and not booleans). An empty alignment is malformed.
  - The provider and the entry disagree: `alignment` is not `null` for a Gemini `model`, `alignment` is not an object for an ElevenLabs `model`, or `language` or `instruction` is not `null` for an ElevenLabs `model`.

Pinned messages, each preceded by `scenevoice synth: FAIL `:

- Scene out of range: `--scene N is out of range (the plan has T scenes)`. `N` is the integer as given, `T` is the plan's scene count; the wording "T scenes" is used for every T, with no singular form.
- Missing `--out`, and in scene mode also a regular file at `--out`: `--out does not exist or is not a directory`.
- Missing `DIR/audio` in scene mode, including a non-directory or a symlink (even to a directory) at `DIR/audio`: `--out/audio does not exist or is not a directory`.
- Refused target: `NNN.wav exists and is not a regular file`.
- Non-regular record (also in a full run): `synth_record.json exists and is not a regular file`.
- Malformed record (D11): `synth_record.json is not a valid synth record (delete it to regenerate without a settings check)`.
- Settings mismatch (D10): `scene N settings differ from synth_record.json: voice recorded "A", passed "B"; model recorded "C", passed "D"`. Only the differing fields are listed, in the order voice, model, language, instruction, joined by `; `. Each present value is in double quotes, after each run of CR and LF characters in it is collapsed to one space. An absent value (`null`) is written as `(none)` without quotes, so a literal instruction `(none)` appears as `"(none)"` and stays distinct. An embedded `"` is shown as is inside the quotes. Values are shown in full. `N` is the integer as given.

Pinned notes, on stderr, each preceded by `scenevoice synth: NOTE ` (not `FAIL`), printed before the provider call. A note does not change the exit code and the run continues:

- No record file: `no settings recorded for scene N (synth_record.json is missing); settings not checked`.
- Record present, no entry for the scene: `no settings recorded for scene N in synth_record.json; settings not checked`.

argparse owns the message for a non-integer `--scene`; the contract pins only exit 2.

## Pre-flight

Without `--scene` all of these happen before the first provider call, in this order:

1. If no `PLAN` is given and stdin is a terminal, fail (exit 1, before any other I/O).
2. Read the plan.
3. Check the plan: the document and shape checks and field rules first, then the 999-scene count, then the body-only limit for every scene: the byte limit for a Gemini model, the character limit for an ElevenLabs model.
4. Check the required environment names.
5. Check the `--out` path and output collisions, in this order: first, a `--out` path that exists as a non-directory fails (existing message). Second, `DIR/audio` fails if it exists as a non-directory or as a symlink (even one that points to a directory, even a dangling one), with `scenevoice synth: FAIL --out/audio exists and is not a real directory`; a missing `DIR/audio` passes. Third, any existing path at `DIR/audio/NNN.wav` fails with `scenevoice synth: FAIL output already exists: audio/001.wav, audio/002.wav` (comma and space separated, plan order, each with the `audio/` prefix). The `DIR/audio` check runs before the collision check so that a symlinked `audio` is reported as such and not as collisions seen through the link. Fourth, a non-regular path at `DIR/synth_record.json` (a directory, a symlink including a dangling one, or any other non-regular file) fails with `scenevoice synth: FAIL synth_record.json exists and is not a regular file`; an absent path or a regular file passes, and the record is not read.
6. Create `DIR/audio`, with parents (so `DIR` too). An existing directory is accepted. Creation happens only here, after every other check has passed, so an invalid plan leaves nothing behind.
7. Prove `DIR/audio` is writable by creating and removing a probe temporary file in it. Successful directory creation alone is not proof.
8. Write the empty record `{"scenes": []}` to `DIR/synth_record.json` (see Synth record, Write points), replacing any regular file there without reading it. This happens after the probe and before the provider factory is built and before the first provider call. Every refusal above has already passed, so a refused run leaves the old record alone.

In a full run, a failure to create the directory, to pass the probe or to write the empty record (step 8) is an operational failure (exit 1) before the first provider call, with nothing synthesized. A write failure after synthesis has started is a later failure under stop-and-keep (see Run and failure semantics).

With `--scene N`, the checks run in this order, all before the provider call:

1. Steps 1 to 3 above: terminal-stdin check, read the plan, check the plan.
2. Check the scene number: `N` must be in 1 to the plan's scene count, else the pinned out-of-range failure. This check runs right after the plan check and before the environment check, so a bad `N` fails without needing credentials.
3. Check the required environment names.
4. Check `--out`: it must exist and be a directory, else the pinned `--out does not exist or is not a directory` failure (a regular file at `--out` gets the same message). Nothing is created. Then check `DIR/audio`: it must exist as a real directory, not a symlink (even to a directory), else the pinned `--out/audio does not exist or is not a directory` failure. Then check the target `DIR/audio/NNN.wav`: absent or a regular file passes; anything else gets the pinned `NNN.wav exists and is not a regular file` failure. These three checks replace the full-run collision check and directory creation, and all run offline before the provider call.
5. Check the record path: a non-regular path at `DIR/synth_record.json` gets the pinned `synth_record.json exists and is not a regular file` failure. An absent path or a regular file passes.
6. Read the record, if the file exists. Check it as a whole (D11), else the pinned malformed-record failure. Then compare the settings for the scene (D10): on a difference, the pinned mismatch failure. With no file, or no entry for the scene, print the matching `NOTE` and go on. Nothing is written yet.
7. Prove `DIR/audio` is writable with the probe temporary file, as above.

Environment names are per provider. A Gemini model needs only `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` and `VERTEX_AUTHORIZATION_KEY`. An ElevenLabs model needs only `ELEVENLABS_API_KEY`. A name is missing when it is unset, empty or whitespace-only. Values come from the process environment, falling back to `.env` in the current working directory; the process environment wins. All missing names are listed in one message, in the order above, and never their values (for example `missing environment variables: ELEVENLABS_API_KEY`). The key never appears in any message.

## Run and failure semantics

Scenes run sequentially in plan order, with one provider call and one WAV per scene. The response acceptance rules and response handling are per provider: see Gemini (Vertex) request and response and ElevenLabs request and response. The stop-and-keep rule and the key rule apply to both providers.

Any response that a provider section rejects, and any provider error, is a provider failure. It stops the run, keeps the WAVs already written, and exits 1. A write failure after synthesis has started follows the same stop-and-keep rule.

No message ever contains an API key, for either provider. Redaction of the project id and tokens is not guaranteed.

## Gemini (Vertex) request and response

This section applies to a Gemini model. The ElevenLabs request is defined under ElevenLabs request and response.

Request:

- Model: the `--model` value, either `gemini-3.8-flash-tts` or `gemini-3.8-flash-lite-tts`. It goes in the request URL path; it is not in the body. The body is identical for both models. API version: `v1` (the path contains `/v1/`).
- `contents[0].parts[0]` holds `text` (the body) and, only when `--instruction` is passed, a sibling key `speechMetadata` whose `style` (`speechMetadata.style`) is the instruction text. With no instruction, `speechMetadata` is omitted.
- The voice is `generationConfig.speechConfig.voiceConfig.voice` (the `--voice` value). The language is `generationConfig.speechConfig.languageCode` (the `--language` value). There is no `prebuiltVoiceConfig` and no `systemInstruction`. The style is never placed under `generationConfig`.
- `languageCode` on 3.8 is documented in Google's Vertex migration guide for the Flash model; it was accepted (`en-GB`) on WS12's first live call on `global`.

Style: The instruction, when supplied, is sent as the style on the text part (see Request above). It is never joined into `text`. There is no `<breath>` tag and no `systemInstruction`: the 3.8 probe got HTTP 400 for `systemInstruction`.

Length limit: The `body` must be at most 8,000 UTF-8 bytes. The check applies to each scene body alone; the instruction does not count toward it. 8,000 is our own conservative cap, inherited from 3.1; it is not a documented 3.8 limit. Every scene is checked before the first provider call. An over-limit scene is rejected, not split. The rejection names every offending ordinal with its byte count, in the form `body over 8000 UTF-8 bytes: ` followed by each ordinal and its byte count, joined by `; ` (for example `body over 8000 UTF-8 bytes: scene 2: 8123 bytes; scene 5: 9001 bytes`).

The 8,000-byte body cap is the only length check. No 3.8 audio-length limit is documented or checked; WS12 records the longest observed duration.

Location: `GOOGLE_CLOUD_LOCATION` stays a required environment name, and its value is used as given. Google documents `global` for both models. WS12's first live call on `global`, on `gemini-3.8-flash-tts` only, succeeded: exit 0, a valid WAV, and `languageCode: en-GB` accepted. The earlier 3.8 probe had run on `us-central1` from `.env` and also succeeded, so both locations have worked. The owner runs on `global`, set in `.env`.

Accepted, not ear-verified: the 28 voices other than Callirrhoe and Charon, and `gemini-3.8-flash-lite-tts`, are accepted by the allowlist and the model list but have not been ear-verified. Earlier 3.8 acceptance is WS12 and WS16, on `gemini-3.8-flash-tts` with Callirrhoe and Charon only. WS10 was on `gemini-3.1-flash-tts-preview`, so it is superseded evidence. Language support per model is unchecked (Flash-Lite lists 101 languages, Flash 130); a provider-side language failure is a provider failure. The 8,000-byte body cap and the 999-scene cap are unchanged for both Gemini models. A live check is deferred (WS19).

Response acceptance. A response is accepted only if all of these hold:

- Its declared media type is `audio/wav`, compared case-insensitively after trimming, with any parameters after `;` ignored. Any other type, including `audio/L16`, is rejected. The type check is a cheap filter; the header check below is the real guard.
- The WAV header, read with the stdlib `wave` module, says 24000 Hz, 1 channel, 16-bit samples and a non-empty data section (frame count above zero). Nothing in the header is trusted beyond what `wave` reads: rate, channels, sample width and frame count.
- The frame bytes actually present equal the declared frame count times the frame width. A truncated body is rejected.

A wrong media type is reported as `provider response rejected: media type must be audio/wav (got X)`, where X is the received declared type made one line, restricted to a safe character set and bounded in length. Validation never raises: every rejection is a provider failure with a message.

Response handling: the response is a JSON document whose first part holding inline data carries a base64 payload. A malformed or truncated header is a provider failure, never a crash. The bytes written are the decoded bytes unchanged, through the atomic write described under Output. Any other response is a provider failure.

## ElevenLabs request and response

This section applies to an ElevenLabs model (`eleven_flash_v2_5` or `eleven_v4`). It was implemented in WS29 (offline, fixture-tested) and live-accepted in WS30 on `eleven_flash_v2_5` only (2026-10-26); `eleven_v4` is not live-accepted.

Request:

- Every request is `POST /v1/text-to-speech/{voice_id}/with-timestamps?output_format=pcm_24000` on the ElevenLabs API host `https://api.elevenlabs.io`. `{voice_id}` is the `--voice` value. The header `xi-api-key` carries `ELEVENLABS_API_KEY`.
- The JSON body has exactly these keys: `text`, `model_id`, `previous_text`, `next_text` and `seed`. `previous_text` and `next_text` are present or absent as the neighbour rules below say.
- `text` is the scene `body` verbatim. Nothing is prepended, and the `title` is not sent. `model_id` is the `--model` value.
- The response is JSON. The audio in it is raw PCM: 24 kHz, mono, 16-bit, little-endian. `synth` wraps it as a WAV with a standard header declaring the same four facts that the Gemini path validates: 24000 Hz, 1 channel, 16 bits, and a frame count above zero. The output file name, layout, atomic write and collision rules are unchanged.

Neighbour text:

- Each request carries, where the neighbour exists, the previous plan scene's `body` as `previous_text` and the next plan scene's `body` as `next_text`. Each is the whole `body` string, never truncated.
- The first scene omits the `previous_text` key and the last scene omits the `next_text` key. The keys are absent, never empty strings. A one-scene plan sends neither.
- With `--scene N`, the neighbours still come from the plan.
- Neighbour texts do not count toward the character limit.
- No limit for these fields is documented, and none has been probed (see Accepted, not probed).
- A scene's audio depends on its neighbours' text. If one scene's body is edited, the neighbours' audio was rendered against the old text and is not refreshed. To refresh it, the operator can regenerate the neighbours with `--scene`. This is an accepted limitation.

Seed:

- The seed is the contract constant `42`, sent as `seed`. It is not an option and is not recorded.
- The same seed and text repeat the audio length and the alignment end times, but not the bytes. A regenerated take can differ in bytes.

Character limits:

- The limits are `eleven_v4` 10,000 characters and `eleven_flash_v2_5` 40,000 characters. They come from ElevenLabs' documentation and are not probed.
- The count is in Unicode code points (the length of the `body` string). The check applies to each scene `body` alone, runs for every scene before the first provider call, rejects and never splits, and names every offender.
- The message, preceded by `scenevoice synth: FAIL `, has the form `body over 10000 characters: scene 2: 10123 characters; scene 5: 12001 characters`. The number after `over` is the limit of the model in use (10000 or 40000). Items are joined by `; `, in plan order.
- The 999-scene count check runs before this check. The byte limit does not apply to an ElevenLabs model, and the character limit does not apply to a Gemini model. The Gemini message `body over 8000 UTF-8 bytes: ...` is unchanged.

Response acceptance. A response is accepted only if all of these hold:

- It is JSON with `audio_base64`, a base64 string that decodes to non-empty PCM of even byte length. The PCM is wrapped as above and passes the existing header validation, including a frame count above zero.
- `alignment` is present as an object holding the three arrays `characters`, `character_start_times_seconds` and `character_end_times_seconds`, all of equal length.
- Every time is a finite, non-negative JSON number (not a boolean). Every character is a string.
- The arrays are not empty. An empty alignment is a provider failure, because a body is never blank.

Deliberately not required: that a start time is not after its end time, that times are monotonic, and that the joined `characters` equal the sent text. They matched in the spike, but digits and audio tags in the alignment are unprobed. The declared media type of the response is not checked: it is JSON, not `audio/wav`. `normalized_alignment` is ignored.

Any other response, and any non-200 status, is a provider failure. It stops the run, keeps the WAVs already written, and exits 1. Validation never raises: every rejection is a provider failure with a message.

Alignment clamp:

- Every start time and end time kept is clamped to the WAV duration, `frames / 24000` seconds, for both ElevenLabs models. `eleven_v4` timings come in 0.08 s steps and its last end can overshoot the audio.
- Each time is converted to a float on acceptance and kept in Python's float representation.
- The kept arrays are the provider's `alignment` (not `normalized_alignment`), after the clamp and with no other change.
- The accepted alignment is kept in the synth record file, whose schema is defined in the Synth record section of this contract.

Error mapping:

- A rejected voice ID gets no special mapping. It is a generic provider failure whose message includes the HTTP status. The key never appears in any message.
- Observed in WS30 against the real API (one request each, all exit 1, no WAV, the empty record left, 0 credits charged per `/v1/history`): a fake key gave `HTTP 401` with `invalid_api_key`; a made-up, well-formed voice ID (`ws30NoSuchVoiceID000`) gave `HTTP 404` with code `voice_not_found` and a message naming the voice ID; the library voice Rachel on the Free tier gave `HTTP 402` with code `paid_plan_required`. The owner accepted the generic form for these three cases. A pinned message for the rejected voice ID is not proposed, because the 404 body already names the voice.

Accepted, not probed:

- Observed in WS30 on `eleven_flash_v2_5` with the premade voice George: a five-scene run (the neighbour fields are sent per the WS29 offline tests, but the request bodies are not logged and `/v1/history` does not show them, so the live run did not observe them), digits in the alignment (the joined alignment characters equalled the plan body in all five scenes, including "169"), the error for a wrong voice ID (see Error mapping), and the default `Python-urllib` User-Agent through the product (HTTP 200).
- Still unprobed: the character limits, the limits of the `previous_text` and `next_text` fields, audio tags in the alignment, `eleven_v4` stitching across neighbours, `eleven_v4` ear quality, a redirect on POST, paid-plan output formats and the full terms of use. Both ElevenLabs models are accepted; only `eleven_flash_v2_5` was ear-verified (one voice, two takes of a scene, five scenes in total).

## Streams and exit codes

- stdout is always empty.
- The full-run final line is unchanged: `scenevoice synth: OK T scenes written to DIR`.
- Per-scene progress, any `NOTE` line and the final OK or FAIL line go to stderr, as `scenevoice synth: ...`. A `NOTE` is `scenevoice synth: NOTE ...`. Each failure is reported as `scenevoice synth: FAIL ...`, the same prefix style as `scenevoice plan: FAIL ...`.
- Exit 0 on success.
- Exit 1 on any operational failure, including a terminal stdin with no `PLAN`: plan, limits (the byte limit and the character limit), environment (including a missing `ELEVENLABS_API_KEY`), collision, filesystem or provider (including an ElevenLabs provider failure and a rejected voice ID), a non-regular `DIR/synth_record.json`, and a failed record write; with `--scene`, also an out-of-range scene number, a missing or non-directory `--out`, a missing, non-directory or symlinked `DIR/audio`, a refused target, a malformed record and a settings mismatch (each with the FAIL prefix).
- Exit 2 for usage errors: a missing `--out`, `--voice` or `--model`, a Gemini voice outside the 30 names, a model outside the four names, a blank `--voice` with an ElevenLabs model, `--language` or `--instruction` passed with an ElevenLabs model, a blank `--instruction` or `--language`, or a non-integer `--scene`. Usage errors happen before any I/O.

## Deferred

- Resume and skip-existing.
- Splitting long scenes.
- Retries and rate limits.
- Library, cloned and designed voices (both providers); providers other than Vertex and ElevenLabs; `eleven_v3` and `eleven_multilingual_v2`; timings from `synth`; forced alignment; a BYOK mechanism.
- Performance notes or any plan change.
- `[Pronunciations]`.
- Audio processing.
