# Align contract

**Status: The 2026-10-27 reopening (Milestone 9, WS31), under which `align` can take line start times from `DIR/synth_record.json` for ElevenLabs scenes (subject to check 5a), was approved by the owner on 2026-10-27 and built in WS32 (offline, fixture-tested). WS32 accepted it on 2026-10-27 on a copy of the WS30 R2 ElevenLabs pack with no provider call: with no `OPENROUTER_API_KEY` in the environment or a `.env`, `align` printed `OK 5 scenes, 25 lines, 0 unmatched, 5 from synth record, 0 transcribed` (zero calls); the record-path starts equal the WS30 alignment values on every line, and Whisper minus record is mean -46.5 ms, median -42 ms, min -226 ms, max +20 ms (a difference between two measurements, not an accuracy verdict); `pack --editor resolve` accepted the output, and the owner's Resolve import and ear check passed. Earlier history: New on 2026-10-08; approved by the owner on 2026-10-08. The command and this contract's rules are built in WS25 (offline, with a fake transcriber). Live acceptance (WS26) is done on 2026-10-09: with a real key, `align` ran on the R2 pack (5 scenes, 25 lines) and the R1 pack (8 scenes, 50 lines), both with 0 unmatched sentences; the owner imported the markers built from the word timings into Resolve 21.1.1 and found them "in the right places with the right comments" (checked by reading the marker text against what was heard, not by a per-line listening spot check), including an R2 pack relocated, zipped and unzipped under a spaced, non-ASCII path. The 402, 429 and 5xx error handling was exercised only against a local stub with invented bodies; the real OpenRouter bodies for those statuses, the base64 size limit, the upstream provider and non-English or respelled scripts remain unmeasured.**

This contract defines the `scenevoice align` command: its CLI surface, environment, constants, check order, streams and exit codes. Later sections (listed by name in the pointers below) add the provider request and response, the failure semantics, the timings file, the sentence and word rules, the `## Record path` section and two worked examples. It builds on the [plan contract](plan-contract.md), which owns the plan shape; the [synth contract](synth-contract.md), which owns the `NNN.wav` format, the environment-names mechanism and the key-redaction sentence; and the [pack contract](pack-contract.md), which owns the plan check, the WAV check and the pack-side read contract for `line_timings.json`. It does not edit or contradict any of them, and it does not authorize implementation or provider calls.

`align` works from the plan and `DIR`. It also reads `DIR/synth_record.json` (the record that `synth` keeps, whose schema the synth contract owns). It never reads the creator script and never rewrites creator text. It is the only command that calls the transcription provider (OpenRouter), and it is no longer the only source of line timings: a scene voiced by ElevenLabs takes its line start times from the record, with no call, when check 5a routes it to the record path (see `## Record path`); otherwise it is transcribed. `pack` stays offline and key-free, ignorant of the record, and never calls `align`.

Accepted limitation: only English (en-X) scripts are supported. Non-English scripts are unsupported.

## Command surface

```
scenevoice align [PLAN] DIR
```

- `DIR` is required: the pack folder. It holds the `audio/NNN.wav` files that `synth` wrote for the plan, and may hold `synth_record.json`. `align` writes `DIR/line_timings.json` and nothing else.
- `PLAN` is optional. When omitted, the plan is read from stdin. A single positional argument is always `DIR`, never `PLAN` (the plan is then read from stdin). Two positionals are `PLAN` then `DIR`, as in the pack contract. If stdin is a terminal and no `PLAN` is given, `align` fails (exit 1, before any other I/O) instead of waiting for input, as `synth` and `pack` do.
- The alignment model is a fixed constant (see "Constants"). There is no model option and no base URL option.
- There is no language option. The language sent in the request is the fixed constant `en`.
  - Whisper auto-detects the language when the request field is omitted: OpenRouter's speech-to-text docs (https://openrouter.ai/docs/guides/overview/multimodal/stt; docs text, not exercised) mark `language` optional and say it is auto-detected when omitted, the probe record says the same, and OpenRouter's announcement describes the field as an optional hint. The probe did not test omitting it: its one working call sent `en`, so auto-detect on our short clips is unmeasured.
  - Pinning `en` removes language detection from the request and matches the only verified call. A non-English script is unsupported (accepted limitation); if detection were used and misfired, words would come back in the wrong language and many sentences would get a null `start_ms` and a NOTE.
- Usage errors (exit 2, before any I/O) cover only argument shape: a missing `DIR`, extra positionals, or an unrecognised option.
- `pack` never calls `align`. Operators run `align` before `pack --editor resolve`, and again after `synth --scene N`. Every run rebuilds every plan scene's timings, from the record or from Whisper; nothing is merged or skipped.

## Environment

`align` needs one name, `OPENROUTER_API_KEY`, and only when at least one scene is transcribed (check 6 runs only then). An ElevenLabs pack whose scenes all take the record path needs no key and no network. Values come from the process environment first, falling back to `.env` in the current working directory; the process environment wins. The name is missing when it is unset, empty or whitespace-only. The message names the variable, never a value.

Only the rules stated in "Environment names" of the synth contract are inherited: a name is missing when it is unset, empty or whitespace-only; the process environment wins; `.env` in the current directory is the fallback; the key never appears in a message. Everything else about reading `.env` is "same loader as synth", with no further rule cited. `.env.example` gets its line for this name in WS25.

## Constants

- Model: `openai/whisper-large-v3-turbo`.
- Language: `en`.
- Per-call timeout: 120 seconds. This is an implementation constant that tests do not assert.
- `MATCH_THRESHOLD`: 50 percent. See `## Matching`.
- Endpoint: see `## Request`.

## Check order

All of these happen in this order. Nothing is written and no provider call is made until checks 1 to 6, including 5a, have passed, so a failure before the calls spends no quota. The numbers 1 to 8 are stable once approved; a new check gets a letter suffix, as pack's 3a and 4a.

1. **Usage** (exit 2, before any I/O): a missing `DIR`, extra positionals or an unrecognised option.
2. **Terminal stdin** (exit 1, before any other I/O): no `PLAN` is given and stdin is a terminal.
3. **Plan**: read the plan and apply the whole plan check of pack-contract check 1 by reference (the document, shape and field rules, then the 999-scene limit, then the title UTF-8 rule). The 999-scene limit applies, as in the synth contract (it keeps `audio/NNN.wav` at three digits). Two differences from the synth contract's plan check: there is no byte limit (the 8,000-byte body limit of synth does not apply, because `align` sends no text to a provider); and the title UTF-8 rule applies even though `align` does not use the title (synth never checks the title because it never sends it).
4. **Paths**: `DIR` must exist as a directory (a symlink to a directory is accepted, as in pack). `DIR/audio` must be a real directory: a missing path, a non-directory or a symlink fails. `DIR/line_timings.json` must be absent or a regular file; a directory, a symlink (including a dangling one) or any other non-regular file fails. This precheck avoids the known collision of a non-regular path at that name; any other write failure in check 8 after the calls (a read-only or full `DIR`, a permission change) is the accepted case stated in check 8. The message names `audio` or `line_timings.json`.
5. **WAVs**: for each plan scene in plan order, read `DIR/audio/NNN.wav` once and validate it by pack-contract check 4 by reference: the regular-file rule, the WAV header conditions of "Response acceptance" in "Gemini (Vertex) request and response" of the synth contract (the ElevenLabs path wraps its PCM and passes the same header validation) and the zero-frame rule, all adopted unconditionally (pack states the zero-frame rule for editor runs only; `align` applies it on every run). Nothing in the WAV check is defined again here. A plan scene with no WAV fails. The bytes read are held in memory for all scenes; the SHA-256 and the request body both come from that same buffer, with no second read. The first failing scene stops the checks, and the message names the scene and the file.
5a. **Record**: read `DIR/synth_record.json` once, then decide routing. Everything here is offline and uses only the plan, the record and the WAV bytes held by check 5.
    - A non-regular path at that name (a directory, a symlink including a dangling one, or any other non-regular file) fails. An absent file is not a failure.
    - A record that is malformed by D11 of the synth contract (adopted by reference; nothing is listed again here) fails. The whole file is validated, not against the plan.
    - Entries for ordinals that are not in the plan are ignored: they are not an error, are not used, and play no part in deciding the pack kind.
    - The pack kind is decided from the entries of plan ordinals only. If any such entry has an ElevenLabs `model`, the pack is an ElevenLabs pack; otherwise it is a Gemini pack. A record whose only ElevenLabs entry is out of plan is therefore a Gemini pack.
    - The outcomes, each deciding as stated:
      - (a) No record file: every scene is transcribed, with one NOTE for the run.
      - (b) A Gemini pack, including a record that is `{"scenes": []}`: every scene is transcribed, with no NOTE; the entries' `sha256` is ignored and missing entries are irrelevant.
      - In an ElevenLabs pack each plan scene is evaluated in plan order by (c) to (g) in exactly this order, and the first that applies decides that scene:
        - (c) The entry for the scene is missing: a failure naming the scene.
        - (d) The entry has a Gemini `model`: the scene is transcribed, its `sha256` is ignored and no NOTE is printed. This is defined, not promised or tested; one provider per script, so mixed-provider packs are unsupported, not rejected.
        - (e) The entry's `sha256` differs from the SHA-256 of the held WAV bytes: a failure naming the scene.
        - (f) The joined `characters` of the entry's `alignment` differ from the scene's plan `body` (exact, raw, no normalisation, because `synth` sends the body verbatim): the scene is transcribed, with one NOTE for that scene.
        - (g) Otherwise the scene takes the record path (`## Record path`), with no provider call, subject to the next rule.
    - A start time that the record path converts, for a scene routed to the record path, must be representable by the millisecond formula; if the computation overflows or is not finite (possible only for a value above about 1.8e305, which D11 accepts as a finite number), the record is unusable for that run and fails. No other element is validated, and a scene transcribed by (d) or (f) is exempt.
    - Per-scene failures ((c), (e) and the overflow rule) are reported for the first failing plan scene. Every 5a failure is a FAIL naming `synth_record.json` and, where there is one, the scene.
6. **Environment**: `OPENROUTER_API_KEY` as in "Environment", checked only when at least one scene is transcribed by 5a. A missing key then fails and names the variable. An all-record pack skips this check.
7. **Provider calls**: one call per transcribed scene, sequential, in plan order, each with the 120 second timeout, using the held bytes; none for a record-path scene. This is the only step that spends quota. A failure stops at the first failing scene and makes no further call; see `## Failure semantics`.
8. **Write**: only after every scene succeeded, write `DIR/line_timings.json` atomically; see `## Timings file`. A read-only or full `DIR` can still fail at temporary-file creation here, after the calls were spent; this is accepted and no writability probe is made.

A failure at checks 1 to 6, including 5a, is a failure before anything is written and before any provider call. The numbers 1 to 8 are unchanged; 5a follows the letter-suffix convention, and routing NOTEs are not printed at 5a (see `### Messages`). A failure at check 7 writes nothing. In every failure no new `line_timings.json` is created and any existing one remains unchanged.

## Streams and exit codes

- stdout is always empty.
- Everything else goes to stderr as `scenevoice align: ...`. The NOTE and OK line shapes are in `### Messages` under `## Failure semantics`. Each failure is `scenevoice align: FAIL ...`, the same prefix style as `scenevoice synth: FAIL ...`.
- Exit 0 on success, with or without NOTE lines.
- Exit 1 on any operational failure: a terminal stdin with no `PLAN`, the plan, limits, `DIR`, `DIR/audio`, `DIR/line_timings.json`, a WAV, the record (a non-regular path, a malformed record, a per-scene `sha256` mismatch or missing entry, or an overflowing start time), the environment, the provider, and the filesystem.
- Exit 2 for usage errors: a missing `DIR`, extra positionals or an unrecognised option. Usage errors happen before any I/O.
- The key never appears in any message.

### Worked examples of check-order failures

All of these are about the order of checks, not message wording; tests assert only the `scenevoice align: FAIL` prefix plus the names.

- Terminal stdin, no plan: `scenevoice align out` with stdin a terminal. Exit 1, before any other I/O; no file is read, no call is made.
- Extra positional: `scenevoice align plan.json out extra`. Exit 2, before any I/O.
- Missing WAV: a three-scene plan whose `out/audio/002.wav` does not exist. Exit 1; the FAIL line names scene 2 and the file `002.wav`; no call is made and nothing is written.
- Timings path is a directory: `out/line_timings.json` exists as a directory. Exit 1; the FAIL line names `line_timings.json`; no call is made and nothing is written.
- Missing key: the plan, `DIR` and all WAVs are good and at least one scene is transcribed, but `OPENROUTER_API_KEY` is unset, empty or whitespace-only in both the process environment and `.env`. Exit 1; the FAIL line names `OPENROUTER_API_KEY`, never a value; no call is made and nothing is written.
- Record `sha256` mismatch (i): an ElevenLabs pack whose record entry for a scene has a `sha256` different from the hash of that scene's WAV. Exit 1 at check 5a; the FAIL line names `synth_record.json` and the scene; no call is made and nothing is written.
- Missing entry (ii): an ElevenLabs pack of three scenes whose record has entries for scenes 1 and 3 but none for scene 2. Exit 1 at check 5a; the FAIL line names `synth_record.json` and scene 2; no call is made and nothing is written.
- Malformed record (iii): `synth_record.json` is malformed by D11 of the synth contract. Exit 1 at check 5a; the FAIL line names `synth_record.json`; no call is made and nothing is written.
- Record path is a directory (iv): `out/synth_record.json` exists as a directory. Exit 1 at check 5a; the FAIL line names `synth_record.json`; no call is made and nothing is written.
- All-record pack, no key (v): an ElevenLabs pack in which every scene takes the record path, with `OPENROUTER_API_KEY` unset. Check 6 is not run, because no scene is transcribed; no call is made; the run can succeed.

## Request

Source: a private probe record (the pre-WS24 probe, 3 calls on 2026-10-08). The request and response facts below are what that probe observed. Where OpenRouter's public OpenAPI text is mentioned, it is said so, and that text was not exercised.

- Endpoint: `POST https://openrouter.ai/api/v1/audio/transcriptions`.
- Header: `Authorization: Bearer <key>`, where `<key>` stands for the value of `OPENROUTER_API_KEY`. Content type is JSON.
- JSON body fields, exactly:
  - `model`: `openai/whisper-large-v3-turbo`.
  - `input_audio`: an object holding `data`, the base64 of the exact WAV bytes (raw base64, not a `data:` URI), and `format`, the string `wav`.
  - `language`: the constant `en`.
  - `response_format`: `verbose_json`.
  - `timestamp_granularities`: the array `["word", "segment"]`.
- One call per transcribed scene, sequential, in plan order, from the bytes held in memory (check 5). The per-call timeout is 120 seconds, an implementation constant that was not tested and that tests do not assert.
- The OpenAPI text also describes a multipart upload (`file`, capped at 25 MB) and a `source_url` form. `align` uses neither; base64 JSON is the route that text gives for larger files. That text was not exercised.
- The OpenAPI text says `verbose_json` is supported only by OpenAI-compatible providers. This was not exercised; see "Routing drift" under `## Response`.

## Response

A 200 response seen in the probe (7.75 s for 16.92 s of audio) is a JSON object with the top-level keys `duration`, `language` (`en`), `segments`, `task`, `text`, `usage` and `words`. `usage` was `{"seconds": 16.92, "cost": 5.63436e-05}`.

- `words[]` is an array of `{word, start, end}`, with `start` and `end` in seconds as floats. The probe had 36 words for 36 script words. Floats carry noise: a start of 0.23999999865889549 is really 0.24 (see the millisecond formula in `## Milliseconds`).
- `word` carries a leading space and keeps attached punctuation (for example ` burning,` and ` instead.`). Numerals arrive as digits (for example ` 169` where a script says "one hundred sixty-nine" or writes `169`). Trim and normalise before matching (see `## Word normalisation`).
- Words were contiguous and non-decreasing in the probe.
- Only `words[].word` and `words[].start` are used. `end`, `text`, `duration`, `language`, `usage` and `task` are not used. The response also carries, per segment, `avg_logprob`, `no_speech_prob`, `compression_ratio`, `temperature`, `tokens` and `seek`; `align` does not use any of them. `segments` is not used and is never keyed on `id`: in the probe all four segments had `id` 0.

### Probe finding on `response_format` (2026-10-08)

A later check after the first probe, 2 hosted calls on an 18.48 s scene (about $0.00012 in total). The evidence is in the same private probe record (2026-10-08, "Follow-up check"); the raw responses were not saved, and the figures are from the printed output of a throwaway script, recorded in that record:

- `response_format` `verbose_json` is required for word timings. A request without `response_format` returned 200 with only `text` and `usage`: no `words` and no `segments`. The `verbose_json` request returned `words` (36) and `segments` (3), with the same keys as the first probe.
- The OpenAPI text says `verbose_json` is supported only by OpenAI-compatible providers. That exclusion was not exercised, and a probe cannot prove it. The serving upstream provider is not visible: the response carried an `X-Generation-Id` header; the CORS expose list names `X-Provider-Name`, but that header was not returned; and a lookup of the generation id returned 404. This is consistent with the upstream provider identity entry under `### Not measured`, which stays.
- A 200 without `words` is a malformed response (below), which is how a request that dropped `verbose_json` or a provider that ignored it would show up.

### Malformed responses

Each of these in a 200 response is a scene failure, exit 1, naming the scene (see `## Failure semantics`):

- the body is not JSON, or is JSON but not an object;
- `words` is absent, empty or not an array;
- a `words` entry is not an object;
- an entry's `word` is not a string;
- an entry's `start` is missing, a boolean, not a number, negative, or non-finite, or so large that its millisecond computation overflows or is not finite (a huge JSON integer raises an overflow instead of giving infinity; either way it is a malformed response, with no traceback);
- `start` values decrease from one word to the next;
- after word normalisation (`## Word normalisation`) drops empty tokens, zero surviving tokens remain (for example a non-empty response holding only punctuation).

Word order is the order of the response, never sorted. Equal consecutive starts are allowed.

### Routing drift

An empty or absent `words` array is also how routing to an upstream provider that returns no word timings would show up. The probe did not capture which upstream provider served the call, so this is not excluded. `align` treats it as the scene failure above rather than writing null starts for every line.

### Not measured

The probe did not measure, and this contract does not state facts about:

- the size limit for base64 JSON. The OpenAPI text gives 25 MB only for the multipart `file` upload; the limit for base64 JSON is undocumented. A typical 30 s scene is about 1.4 MB as a WAV, and the base64 JSON body is about 4/3 of that (about 1.9 MB), which is what an undocumented JSON limit would apply to;
- behaviour on 402 (credits), 429 and 5xx against the real service. The OpenAPI text lists other statuses; none was exercised live, so no real body is given here for them. WS26 exercised these statuses only against a local stub with invented bodies (the command exits 1, names the scene and status, writes nothing);
- timestamp accuracy against what is heard beyond WS26's check. In WS26 (2026-10-09) the owner read the marker text in Resolve against what was heard on R2 and R1 and found the markers "in the right places with the right comments"; no per-line listening table spot check was made on the other lines;
- how the record-path start times compare with what is heard. They were compared with Whisper's on one `eleven_flash_v2_5` pack only (mean difference about -46 ms over 25 sentences); this is two close measurements, not a claim that either is more accurate. `eleven_v4` start times (quantised to 0.08 s) and audio tags are not live-accepted: a tag or a normalised text shows up as a joined-characters mismatch and is transcribed (outcome (f)), with no other handling;
- scripts with respelled pronunciations, and non-English scripts;
- long scenes;
- which upstream provider served the call. WS26 recorded, for all 13 live calls, no provider or model field in the body and no provider header, only an `X-Generation-Id` header besides generic CDN headers (`Server`, `CF-RAY`, `Server-Timing`); the reported cost per audio second fell in two tiers about 3.3 times apart, which may point to two upstreams, but the provider stays unavailable.

No size preflight: `align` does not check the size of a scene's audio before the call. A provider rejection of an oversized scene fails that scene by number. If a size limit is ever added, it must be labelled as self-imposed in the message. There is no chunking.

## Failure semantics

The run is all-or-nothing. After the pre-call checks (1 to 6, including 5a) have passed, any of the following is a scene failure: exit 1, nothing written, and the FAIL line names the scene number and the HTTP status where there is one.

- any transport error (DNS, connection, TLS);
- any non-200 status, including 401, 402, 429 and any other 4xx or 5xx;
- a timeout;
- a malformed response (see `### Malformed responses` under `## Response`), including an absent, empty or unusable `words` array.

Rules:

- A failure stops the run at the first failing scene. There is no retry and no further call.
- Nothing is written. No `line_timings.json` is created or changed, and an existing one stays as it was.
- Every run rebuilds every plan scene's timings, from the record or from Whisper. A scene whose `line_timings.json` hash is still fresh is not skipped (the record path has no hash-skip either), and there is no merge with an existing file.
- The two failure bodies the probe saw are both `{"error": {"message", "code"}}`:
  - 401, a bad key: `{"error": {"message": "User not found.", "code": 401}}`;
  - 400, an unknown model: `{"error": {"message": "Model openai/whisper-no-such-model does not exist", "code": 400}}`.
  Nothing else is known about error bodies. The message does not depend on them: it names the scene and the status, and any provider text shown is redacted first.
- A scene whose Whisper word list is empty or has no surviving token is a scene failure (exit 1). This differs from a script sentence that has zero tokens (an ellipsis or dash-only segment, for example: in `Hello. ... Next.` the `...` is isolated as its own sentence by a terminator run plus whitespace): that sentence gets a null `start_ms` and a NOTE, and still counts toward `<n>`, exit 0. The matching rule for the second case is in `## Matching`.

### Redaction

`align`'s own rule: the value of `OPENROUTER_API_KEY` is redacted from any provider text before it is shown, so the key never appears in any message. From the synth contract only two things are cited: its sentence "No message ever contains the API key", and its non-guarantee that project id and token redaction is not guaranteed; the same non-guarantee holds here. The rule is not that provider error bodies are echoed verbatim.

### Messages

All go to stderr as `scenevoice align: ...`; stdout is empty. Wording beyond the names below is illustrative.

- FAIL: `scenevoice align: FAIL ...`, one line, then exit 1. What it names:
  - a provider or response failure: the scene number and, where there is one, the HTTP status;
  - a missing or unusable WAV (check 5): the scene number and the file name;
  - the `audio` directory or `line_timings.json` (check 4): `audio` or `line_timings.json`;
  - the record (check 5a): `synth_record.json` and, for a per-scene cause (a missing entry, a `sha256` mismatch, an overflowing start time), the scene. The missing-entry and `sha256`-mismatch FAILs also tell the operator to re-run `synth --scene N` for that scene;
  - the environment (check 6): `OPENROUTER_API_KEY`;
  - the plan (check 3) and the terminal stdin (check 2): `FAIL ` followed by the one-line message of the plan check or the stdin check, unchanged (tests assert the prefix and a name that message carries).
- NOTE: `scenevoice align: NOTE ...`, one per script line left unmatched or with a null `start_ms`, naming the scene and the line. NOTEs are collected and emitted before the final line, in plan scene order and then line order. A NOTE never changes the exit code. NOTEs are produced only after every scene's call has succeeded (the run is all-or-nothing, so no matching result is used or shown before then): a failure at check 7 prints no NOTE, and a failure at check 8 (a write failure) prints the collected NOTEs before the FAIL line, as pack prints its collected NOTEs before a later FAIL.
- Routing NOTEs (check 5a outcomes) are collected the same way and printed after every call succeeded, never at 5a: a failure at check 7 prints no routing NOTE, and a failure at check 8 prints the collected routing NOTEs, with the line NOTEs, before the FAIL line. The order is: the no-file NOTE first (outcome (a), one per run, for example `scenevoice align: NOTE no synth_record.json, all scenes transcribed`); then, per scene in plan order, that scene's character-mismatch NOTE (outcome (f), for example `scenevoice align: NOTE scene 2: alignment text differs from plan body, transcribed`) before that scene's line NOTEs. A Gemini pack, including the empty record `{"scenes": []}`, gets no routing NOTE; only an absent file does.
- OK: one final line, `scenevoice align: OK ...`, carrying the scene count, the line count, the unmatched count and the two source counts (scenes taken from the synth record, scenes transcribed). The source counts are scene counts and sum to the scene count; unmatched counts every line with a null `start_ms`, including zero-token sentences on the record path. Exit 0, with or without NOTEs.
- Tests assert only the `scenevoice align: OK`, `scenevoice align: NOTE` or `scenevoice align: FAIL` prefix plus the names above, as pack's tests do.

Illustration (wording is illustrative):

```
scenevoice align: NOTE scene 2 line 3: no match, start_ms null
scenevoice align: OK 3 scenes, 11 lines, 1 unmatched, 0 from synth record, 3 transcribed
```

(The Whisper OK illustration above is for a Gemini pack; with no record file the no-file NOTE would also be printed.)

Record case (wording is illustrative):

```
scenevoice align: OK 5 scenes, 25 lines, 0 unmatched, 5 from synth record, 0 transcribed
```

### Quota

Hosted calls cost quota, so the number of calls is part of the contract:

- a successful run makes exactly one call per transcribed scene, so exactly N calls when all N scenes are transcribed and zero calls for an all-record ElevenLabs pack;
- a failed run stops at the first failing scene and makes no further calls (no retry), so it spends at most the calls made up to and including that scene;
- a failure before the calls (checks 1 to 6, including 5a) makes zero calls;
- observed billing was about $0.012 per audio hour in the probes ($0.0000563 for 16.92 s of audio, $0.0000615 for 18.48 s); OpenRouter's public list price is $0.04 per audio hour (not observed);
- a check-8 write failure happens after all calls were spent (as check 8 states).

Record-path example: a five-scene ElevenLabs pack in which every scene takes the record path makes zero calls and spends no quota, with or without a key.

Failure example: a 401 on scene 2 of 3. Exit 1; the FAIL line names scene 2 and status 401; scene 1's call is already spent, scene 3 is never called; nothing is written.

## Timings file

`align` writes one file, `DIR/line_timings.json`. It is a derived cache: an existing regular file is always overwritten (no collision refusal, unlike the WAVs), while a non-regular path at that name (a directory, a symlink or any other non-regular file) is refused in check 4 before any call; and it holds nothing that cannot be rebuilt by running `align` again. The pack contract owns what `pack` reads from it ("Line timings (read-only input)"); this section is the full schema that satisfies that lower bound. `align` reads `DIR/synth_record.json` only in check 5a and never writes it; `line_timings.json` has the same schema and the same serialisation rules whatever the source of its start times (record or transcription); the `start_ms` values naturally depend on the source.

**Write**

- Written only after every scene succeeded (check 8). The bytes go to a temporary file in `DIR` and are then renamed onto `line_timings.json` in one atomic step, so `pack` never sees a half-written file.
- The temporary name never ends in `.json`, so a leftover can never be read as `line_timings.json`. Removing the temporary file after a failure is best-effort, like pack's check 5; a leftover is harmless.
- A failure at any earlier point creates no file and leaves an existing `line_timings.json` as it was.

**Schema**

- The top level is a wrapper object with a `scenes` key and no other top-level key. A bare array at the top level would send `pack` to exit 1, so it is never written.
- `scenes` holds one entry per plan scene, in plan order, never merged with an earlier file.
- Each entry is an object with exactly `ordinal`, `sha256` and `lines`:
  - `ordinal`: the plan scene's integer ordinal.
  - `sha256`: 64 lowercase hexadecimal characters, the SHA-256 of the exact `audio/NNN.wav` bytes that were sent to the provider, or, for a scene on the record path where nothing is sent, the held bytes. It is taken from the same in-memory buffer as the request body (check 5) and as the comparison with the record's `sha256` (check 5a, outcome (e)), with no second read, so the hash describes what was aligned.
  - `lines`: an array of objects, one per sentence of that scene's body in order (the splitting rule is in `## Sentence splitting`), each with exactly `text` and `start_ms`:
    - `text`: the sentence as a string.
    - `start_ms`: a non-negative integer (see `## Milliseconds`), or null when the sentence was not matched. A sentence with zero tokens is also null, and it still takes its place in the array, so the 1-based `<n>` of every later line is unchanged.
- No extra field at any level. `pack` would ignore one, but nothing here needs one, and fields such as a language, a model or a timestamp would make the bytes vary from run to run.
- Which input is malformed is decided by the pack-side rules, not by this file; the table below only shows that `align` writes nothing those rules would reject.

**Byte facts**

The file is what Python's `json.dumps` with `indent=2` and `ensure_ascii` off produces for the structure above, encoded as UTF-8, plus one final LF. In words, so a golden fixture needs no library:

- UTF-8 with no byte order mark, 2-space indent, a newline after each opening bracket of a non-empty array or object, and nothing between the brackets of an empty one. The item separator is a bare `,` at the end of a line, never `, `. The key separator is `: `. An empty array is `[]`.
- Keys are in this fixed order, and every object carries all of its keys: `scenes`; then `ordinal`, `sha256`, `lines`; then `text`, `start_ms`.
- `ensure_ascii` is off, so a non-ASCII character is written as itself (its UTF-8 bytes), not as `\uXXXX`.
- In strings, double quote and backslash are escaped as `\"` and `\\`. LF, CR, TAB, backspace and form feed are written as `\n`, `\r`, `\t`, `\b` and `\f`. Every other control character below U+0020 is written as lowercase `\u00XX`. Everything else, including `/`, 0x7f, U+2028 and U+2029, is written as itself.
- `start_ms` is a JSON integer with no decimal point, or `null`.
- The file is written as bytes, with no newline translation, so the only line ending is LF. Exactly one LF follows the final closing brace, and the file ends with exactly that one LF.

Worked example (data; the `sha256` is a stand-in of 64 characters). The sentence in scene 2 contains a double quote and one non-ASCII character (`é`, which is the two bytes `c3 a9` in the file):

```
{
  "scenes": [
    {
      "ordinal": 2,
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "lines": [
        {
          "text": "She said \"café\" twice.",
          "start_ms": 240
        },
        {
          "text": "Next one.",
          "start_ms": null
        }
      ]
    }
  ]
}
```

The text line `"text": "She said \"café\" twice.",` is the exact bytes of that line: ten spaces of indent, the key, `: `, the string with each double quote preceded by a backslash and `é` as `c3 a9`, then a bare comma. The `start_ms` line of a null start reads `"start_ms": null` with no comma, and the last line of the file is `}` followed by one LF.

### Pack cross-check

Each row is one thing `pack` requires of the file (pack-contract "Line timings (read-only input)", rules (b) and (c)) and how `align` satisfies it. None of them is relaxed here, and `align` never writes a file that sends `pack` to exit 1.

| Pack-side requirement | How `align` satisfies it |
| --- | --- |
| The file is one JSON document: UTF-8, no BOM, no trailing data | The file is UTF-8, written with no BOM, and holds one document followed by exactly one LF (whitespace, so no data follows it). |
| No duplicate keys | Every object is written with a fixed key set, each key once. |
| No `NaN` | No float is written at all: `start_ms` is an integer or null, a non-finite `start` in a response fails the scene (`## Response`, malformed responses) before anything is written, and a start time taken from the record is a finite number (the synth contract's D11) that the record path converts to an integer or fails at check 5a. |
| The top level is an object with a `scenes` array | The wrapper `{"scenes": [...]}` is always written, with `scenes` an array and no other top-level key. |
| Each entry and each line is an object | Entries and lines are always objects with the exact keys above. |
| `ordinal` is a JSON integer | It is the plan scene's ordinal, written as an integer. |
| `sha256` is exactly 64 lowercase hexadecimal characters | It is the SHA-256 of the held WAV bytes in lowercase hexadecimal, 64 characters. It also equals the hash of the current `audio/NNN.wav` while that file is unchanged, so `pack` finds the entry fresh. |
| `lines` is an array of objects | Always an array; each element is an object with `text` and `start_ms`. |
| `text` is a string | The collapsed sentence, always a string. |
| `text` can be encoded as UTF-8 | Plan text is already UTF-8 (the plan check, and the title UTF-8 rule, apply in check 3), and `text` is built from it, so no lone surrogate can be present. |
| `start_ms` is a non-negative JSON integer or null | An integer from the formula in `## Milliseconds` (never negative, never a float, never a boolean) or null. |
| A null `start_ms` still counts toward `<n>` | `lines` holds one element per sentence, in order, with a null `start_ms` for an unmatched or zero-token sentence; the array position plus one is `<n>`. Nothing is dropped or renumbered. |
| An `ordinal` is not repeated in two entries | One entry per plan scene, and plan ordinals are unique, so no ordinal repeats. |
| Unknown fields are ignored | No extra field is written, so this tolerance is never used. |
| An entry for a scene not in the plan is ignored | None is written: only plan scenes get an entry. |
| A scene with an empty `lines` array is allowed | Not a case to rely on: a plan body is non-blank, so every entry has at least one line. |

## Milliseconds

`start_ms` is a start time in seconds, multiplied by 1000, plus one half, rounded down to the next integer at or below it. The start time is a Whisper word's `start` (the matching path) or an alignment start time from the synth record (the record path, `## Record path`); one formula and one set of examples serve both. The computation is on the parsed float, not on the response text or the record's text. It is never the language's round-half-even `round()`. The result is a non-negative integer, which is what `pack` reads.

- The probe returned float noise: a `start` of 0.23999999865889549 becomes about 240.49999866 after multiplying and adding one half, which rounds down to 240. (Truncating instead would give 239.)
- Either side of a half millisecond: a `start` of 1.2344 is 1234.4 milliseconds, which becomes 1234; a `start` of 1.2346 is 1234.6 milliseconds, which becomes 1235.
- A `start` of 0 gives 0.
- A `start` whose millisecond computation overflows or is not finite (a huge JSON integer overflows instead of giving infinity) is not rounded: it is a malformed response and fails the scene (exit 1, no traceback) (the rule is in `### Malformed responses` under `## Response`). The same computation failing on a start time the record path converts is the check 5a overflow failure, exit 1, no call.
- A record start time of 0.24 is 240.5 after multiplying and adding one half, which becomes 240; one of 1.5 becomes 1500.

## Sentence splitting

A scene's plan `body` is split into sentences by the rule below. Each sentence becomes one element of that scene's `lines` array (see `## Timings file`), in order. No splitting library is used and no language-specific handling is applied.

"Whitespace" here is Unicode White_Space, exactly as the "Lexical rules" of the [script contract](script-contract.md) use that term (reused by reference; no whitespace set is listed again here). Two consequences an implementer must not miss: U+001C to U+001F are not White_Space, so a library's default whitespace split must not be relied on; and for the blank-line rule only LF counts as a newline, a CRLF pair counting as one LF, while a lone CR, U+0085, U+2028 and U+2029 are ordinary whitespace. (The script contract rejects CR in a script; a plan body is not guaranteed to have been checked that way, so CRLF is stated defensively.)

The rule, in words:

- A sentence ends after a run of one or more of `.`, `!` and `?`, optionally followed by closing characters, when whitespace follows. The closing characters are the straight double quote, the straight single quote, `)`, `]`, and the typographic closers U+201D (right double quotation mark) and U+2019 (right single quotation mark). The terminator run and its closers stay with the sentence they end.
- A blank line is always a boundary, with or without a terminator before it. A blank line is a whitespace run that holds two or more LFs.
- The end of the body is a boundary, so the last sentence needs no whitespace after its terminator.
- A terminator not followed by whitespace is not a boundary, so `3.5` and `One.Two` stay whole.
- Empty segments are dropped: leading whitespace, and the empty remainder after a final terminator plus trailing whitespace, produce no sentence.

The line `text` is the sentence with every whitespace run, including a single hard-wrap newline, collapsed to one space and trimmed at both ends. It becomes the marker name and comment, so it is part of the byte oracle.

Examples (derived by running a reference implementation of this rule; `\n` and `\r\n` stand for the line break written out):

| Case | Body | Resulting `text` values |
| --- | --- | --- |
| Closing quote, straight | `He said, "Stop." Then he left.` | `He said, "Stop."` and `Then he left.` |
| Closing quote, U+201D | `He said, “Stop.” Then he left.` | `He said, “Stop.”` and `Then he left.` |
| Blank line, no terminator | `Welcome back\n\nToday we start. It is easy.` | `Welcome back`, `Today we start.` and `It is easy.` |
| CRLF as one LF | `First line.\r\nSecond line.` | `First line.` and `Second line.` |
| CRLF blank line | `Heading without stop\r\n\r\nNext part.` | `Heading without stop` and `Next part.` |
| Hard-wrap newline | `This sentence is long\nand wraps here. Next one!` | `This sentence is long and wraps here.` and `Next one!` |
| Whitespace runs collapsed | two spaces, a tab and U+00A0 inside a sentence, as in `Two  spaces<TAB>and a<NBSP>nbsp here.  Done.` | `Two spaces and a nbsp here.` and `Done.` |
| Leading and trailing whitespace | a body of leading spaces and a newline, `Hello there.`, then a space and a newline | `Hello there.` only |
| Decimal, no space after the point | `It costs 3.5 dollars. Fine.` | `It costs 3.5 dollars.` and `Fine.` |
| Ellipsis | `Wait... what? Yes.` | `Wait...`, `what?` and `Yes.` |
| Abbreviation (accepted wrong split) | `Dr. Smith arrived. He sat down.` | `Dr.`, `Smith arrived.` and `He sat down.` |

Accepted limitation: an abbreviation such as `Dr.` or `U.S.` followed by a space is split as if it ended a sentence, and so is any number or word followed by a point and a space that is not a real sentence end. This is the price of using no library. The wrong split cannot misplace audio: the audio is never cut at a sentence boundary, because the sentence split decides only how many marker lines a scene has and which words each line is matched on. A wrong split adds one extra navigation marker or shifts where one starts; the words are still matched in order against the same spoken audio, and a fragment that matches too few words gets a null `start_ms` and a NOTE under `## Matching` in most cases; a wrong time is still possible, as stated under `## Word normalisation`.

A body with no sentence would give `lines: []`. That case is defensive and unreachable: the plan check requires a body with at least one code point outside White_Space, so at least one sentence exists. No test fixture is promised for it.

## Word normalisation

Matching compares words, not text, so both sides are reduced to tokens by the same fixed order of steps. Both the script sentences (after the splitting above) and Whisper's `words[].word` go through it. The order is:

1. Trim a Whisper `word` of its leading space first (a script sentence is already trimmed).
2. Split on Unicode White_Space, as defined for `## Sentence splitting` (reused, not re-listed; U+001C to U+001F are not White_Space and do not split).
3. Lowercase each piece with Python `str.lower()` semantics (not `casefold`: `ß` stays `ß` and is then dropped as non-ASCII by the next step).
4. Strip, in place, every character that is not `a` to `z`, `0` to `9` or the apostrophe `'` (U+0027). Nothing is inserted where a character was removed.
5. Drop every piece that is now empty.

Because stripping happens in place, joined words fuse into one token. Examples (derived by running a reference implementation of the five steps):

| Input | Token |
| --- | --- |
| `word—word` (em dash U+2014) | `wordword` |
| `well-known` | `wellknown` |
| `3.5` | `35` |
| `Hello,` | `hello` |
| ` burning,` (Whisper, leading space) | `burning` |
| `don't` (straight apostrophe) | `don't` |
| `—` alone, or `...` alone | no token |

When one Whisper `word` holds internal whitespace and so yields several tokens, all of them share that word's start time. Whisper is not expected to do this; the rule only keeps the result defined. A Whisper `word` that yields no token is removed, and the surviving tokens keep their own start times.

Accepted limitations:

- The curly apostrophe U+2019 is dropped, not folded to `'`. A script with `don’t` becomes the token `dont`, while Whisper's `don't` stays `don't`, so the two do not match and such a word may leave its sentence short of the threshold. A script written with the straight apostrophe matches.
- Characters outside `a` to `z`, `0` to `9` and the apostrophe are dropped after lowercasing, so nearly every non-ASCII letter goes: `café` becomes `caf`. A few characters that lowercase to ASCII survive as that letter: U+212A KELVIN SIGN lowercases to `k`, while `İ` (U+0130) lowercases to `i` plus a combining dot U+0307, and the dot is dropped. Accented or non-Latin words may therefore fail to match on either side.
- As a result, non-English scripts are unsupported (see the limitation at the top and the fixed language `en`).

Both limitations lower the number of matched words and usually show up as null starts with NOTEs, but a plausible wrong start time is possible: stripping can make different words collide, and the 50% threshold can still accept a sentence on a collided word. Live accuracy against what is heard is not measured, and WS26 checks it on a real script. The matching rule that consumes the tokens is in `## Matching`.

## Record path

A scene that check 5a routes to the record path (outcome (g)) takes its line start times from the alignment in its entry of `DIR/synth_record.json`, with no provider call and no matching. The record's schema belongs to the synth contract; this section says only how `align` reads a start time from it. The result is the same `line_timings.json` as for a transcribed scene.

**Rules**

- The sentences are those of `## Sentence splitting`, from the scene's plan `body`, in order. Each becomes one line, with the same `text` as on the matching path.
- A sentence's start is the start time of its first non-whitespace character. "Whitespace" is Unicode White_Space exactly as `## Sentence splitting` defines it (by reference, not restated; in particular U+001C to U+001F are not whitespace, so a library's `\S` is not the definition).
- The offset of that character is a character offset on the original body, as plan reading delivers it, counted from the start of the body: the position where `## Sentence splitting` delimits that sentence's segment on the body, plus the character's position inside the segment. It is never found by searching the body for the sentence's `text`: a search gives the wrong offset for a repeated sentence (in `Yes. Yes.` the second sentence would get offset 0) and cannot find a `text` whose whitespace runs were collapsed. The CRLF-as-one-LF handling belongs to splitting and does not change the body, so an offset is never taken on a text with CRLF replaced.
- An offset maps to an array index by cumulative element length, counted in characters (code points), the same unit as the body offset. The entry's `characters` is an array of strings, and an element is checked only to be a string, not to be one code point, so the array index and the body offset can differ. Walking the elements in order and adding their lengths, the element that contains the offset (the first whose cumulative length is greater than the offset) supplies the start time: the entry's `character_start_times_seconds` value at that element's index. When the offset falls inside a multi-code-point element, that element's start time is used.
- A sentence with leading or trailing whitespace is handled without reading past the end: the first non-whitespace character exists for every non-empty sentence, and a trailing run of whitespace is never indexed. The start time of the whitespace before a sentence is never used.
- The alignment is the entry's `alignment`; `normalized_alignment` is not stored in the record and is never used.
- The start time is converted by `## Milliseconds`. A start time of 0.23999999865889549 becomes 240; the record is not rounded any other way.
- Matching is skipped. Word normalisation and `MATCH_THRESHOLD` do not apply, so no sentence is unmatched for a low match ratio.
- A sentence with zero tokens (`## Word normalisation`) keeps `start_ms: null` and its NOTE, exactly as under `## Matching`, and still takes its place in `lines`, so the 1-based `<n>` of every later sentence is unchanged. It counts as unmatched in the OK line. Its start is not converted, so it is not subject to the overflow check.
- `sha256` in `line_timings.json` is the SHA-256 of the held WAV bytes, as for every scene.
- The entry is used only when the joined `characters` of its `alignment` equal the plan `body` exactly (outcome (f)). The test lives in `align`, not in the synth contract, because that contract requires the arrays to have equal length and the elements to be strings, but does not require the joined characters to equal the body (audio tags and normalisation can differ). Equal means raw equality of the two strings, with no normalisation, since `synth` sends the body verbatim. Where it fails, the scene is transcribed instead.
- A start time that this path converts must be representable by the millisecond formula. If it is not (the computation overflows or is not finite, possible only for a value above about 1.8e305 in a hand-edited record), the record is unusable for that run: check 5a fails naming `synth_record.json` and the scene, exit 1, no call. Only starts the path converts are checked; a scene transcribed by outcome (d) or (f) is exempt.

**Mini-example** (data, derived by hand)

The body is `Hi there. Go on.`, which `## Sentence splitting` splits into `Hi there.` and `Go on.`. The record's `characters` has five elements, `Hi`, ` there.`, ` ` (one space), `Go` and ` on.`, so the lengths are 2, 7, 1, 2 and 4 and the cumulative lengths are 2, 9, 10, 12 and 16. The joined text is `Hi there. Go on.`, which equals the body, so the scene takes the record path. The start times of the five elements are 0.23999999865889549, 0.5, 1.1, 1.2344 and 1.6.

- `Hi there.` starts at body offset 0. Offset 0 is below the first cumulative length (2), so element 0 supplies it: 0.23999999865889549 seconds, which becomes 240.
- `Go on.` starts at body offset 10: the first non-whitespace character after the space at offset 9 is `G`. Offset 10 is not below 2, 9 or 10, and is below 12, so element 3 (`Go`, which holds `G`) supplies it: 1.2344 seconds, which becomes 1234.

Here the array has five elements for sixteen characters, so reading the start time at index 10 (a plain per-character index) would be past the end of the array; the cumulative-length walk is what makes the example come out.

## Matching

Matching decides which Whisper word each script sentence starts at. It, and `MATCH_THRESHOLD` below, apply to transcribed scenes only; a scene on the record path is not matched (`## Record path`). It consumes the tokens of `## Word normalisation` and the sentences of `## Sentence splitting`.

**Reference.** The script's token sequence is aligned to Whisper's with the Python standard-library call `difflib.SequenceMatcher(None, script_words, heard_words, autojunk=False)`, and the result of its `get_matching_blocks()` is the normative reference. Whatever that call returns is the answer, ties included: among the longest common blocks it takes the one earliest in the script, then the one earliest in the heard words, and then repeats the same choice on the stretch to the left and on the stretch to the right. Any other implementation must agree with that output on every input, so no tie-breaking rule is restated here.

**What is matched.**

- Matching runs once per scene, on the whole scene's token sequence: the tokens of all of the scene's sentences, concatenated in order, each token remembering the sentence it came from. It does not run per sentence, so a word the speaker moved across a sentence boundary is still matched.
- The heard sequence is Whisper's `words[]` in response order, each word reduced to tokens by `## Word normalisation`. A word that normalises to nothing is removed, and every surviving token keeps its own start time. A word that yields several tokens gives them all that word's start.
- A token is matched when it lies inside one of the matching blocks. The matched count of a sentence is the number of its tokens that are matched.

**Matched or not.** A sentence is MATCHED when its matched count times 2 is at least its token count (at least 50% of its tokens). `MATCH_THRESHOLD` is that 50%; it was a first value and WS26 (2026-10-09) kept it: on the live R2 and R1 runs all 75 sentences matched with no NOTEs, so there is no evidence for changing the threshold (per-sentence match ratios were not recorded).

- A MATCHED sentence's `start_ms` comes from the start of the first matched word of the sentence, the one earliest in the sentence, not the earliest in the scene, converted by the formula in `## Milliseconds`.
- A sentence below the threshold gets a null `start_ms` and a NOTE naming the scene and the line (the shapes are in `### Messages` under `## Failure semantics`). The run still exits 0.
- A script sentence with zero tokens (an ellipsis or dash-only segment isolated by a terminator run plus whitespace, as in `Hello. ... Next.`, by a blank line, or by a body that is just that token) always gets a null `start_ms` and a NOTE, is never MATCHED, and still takes its place in `lines`, so the 1-based `<n>` of every later sentence is unchanged.

**Not the same as an empty Whisper list.** A scene whose Whisper word list has zero surviving tokens after normalisation (empty, or only punctuation) is a scene failure: exit 1, naming the scene, nothing written. That case is in `### Malformed responses` under `## Response`. It differs from an empty script sentence above: a sentence with nothing to match is a NOTE and exit 0, a response with nothing heard is a failed scene.

A body with no sentence would give `lines: []`. As stated under `## Sentence splitting`, that is defensive and unreachable, and no fixture is promised for it.

### Tie example

Script words `the cat and the dog`, heard words `the dog and the cat`. Running the reference gives one block of size 2 (script position 0, heard position 3, the words `the cat`) and the terminating empty block at script position 5, heard position 5. Other blocks of size 2 exist (`and the` at script 2 and heard 2, and `the dog` at script 3 and heard 0), but the one earliest in the script wins. The stretch to its left is empty, and the stretch to its right holds no heard words at all (the block ends at the last heard word), so nothing more is matched.

So only `the cat` is matched: 2 of 5 tokens. A sentence with that text, `The cat and the dog.`, would have 2 times 2 = 4, which is less than 5, so it is below the threshold (40 percent) and gets a null `start_ms` and a NOTE. This is what the reference gives; an implementation that picked another block of size 2 would disagree with it.

## Worked example

Every value below was derived by running the splitting, tokenising and matching rules with the standard-library reference, not by hand alone.

**Plan** (two scenes):

- Scene 1, title `Opening`, body `Welcome back. Today we start.`
- Scene 2, title `Tips`, body `Keep it simple. See you next time.`

**Files.** `out/audio/001.wav` and `out/audio/002.wav`, both valid WAVs. Their SHA-256 values in the example are illustrative placeholders of 64 characters (sixty-four `1` characters for scene 1, sixty-four `2` characters for scene 2), not the hashes of real bytes.

**Sentences** (`## Sentence splitting`): scene 1 has `Welcome back.` and `Today we start.`; scene 2 has `Keep it simple.` and `See you next time.`.

**Tokens** (`## Word normalisation`): scene 1 has `welcome back` and `today we start`; scene 2 has `keep it simple` and `see you next time`.

**Whisper words, scene 1** (word, start in seconds): ` Welcome` 0.23999999865889549, ` back.` 0.62, ` Today` 1.2344, ` we` 1.6, ` start.` 1.86. Their tokens are the same five as the script's, so one block covers all five: both sentences are fully matched.

- `Welcome back.` is 2 of 2; its first matched word is `welcome`, 0.23999999865889549 seconds, which becomes 240 milliseconds.
- `Today we start.` is 3 of 3; its first matched word is `today`, 1.2344 seconds, which becomes 1234 milliseconds.

**Whisper words, scene 2**: ` Keep` 0.12, ` it` 0.3, ` simple.` 0.5, ` Sue` 1.9, ` you` 2.1, ` nexus.` 2.4. The reference gives a block of three (`keep it simple`) and a block of one (`you`); `sue` and `nexus` match nothing, and `see`, `next` and `time` are left over.

- `Keep it simple.` is 3 of 3; its first matched word is `keep`, 0.12 seconds, which becomes 120 milliseconds.
- `See you next time.` is 1 of 4, because only `you` is matched. 1 times 2 is 2, which is less than 4, so it is below the threshold (25 percent): `start_ms` is null and it gets a NOTE.

**Result.** `out/line_timings.json` has the wrapper key `scenes`, with entries in plan order and the keys in the fixed order of `## Timings file`, an indent of 2, and exactly one LF after the final brace. Exactly one line is null:

```
{
  "scenes": [
    {
      "ordinal": 1,
      "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
      "lines": [
        {
          "text": "Welcome back.",
          "start_ms": 240
        },
        {
          "text": "Today we start.",
          "start_ms": 1234
        }
      ]
    },
    {
      "ordinal": 2,
      "sha256": "2222222222222222222222222222222222222222222222222222222222222222",
      "lines": [
        {
          "text": "Keep it simple.",
          "start_ms": 120
        },
        {
          "text": "See you next time.",
          "start_ms": null
        }
      ]
    }
  ]
}
```

**stderr** (wording illustrative, shapes as in `### Messages`; stdout is empty). There is no `synth_record.json` in `out`, so outcome (a) applies: the per-run routing NOTE comes first, then the line NOTE:

```
scenevoice align: NOTE no synth_record.json, all scenes transcribed
scenevoice align: NOTE scene 2 line 2: no match, start_ms null
scenevoice align: OK 2 scenes, 4 lines, 1 unmatched, 0 from synth record, 2 transcribed
```

Exit code 0. The run made exactly 2 provider calls.

## Worked example (record path)

An ElevenLabs pack with the same plan and the same two bodies as the first example, aligned from the record, with `OPENROUTER_API_KEY` unset. Every value was checked by hand against `## Record path` and `## Milliseconds`.

**Plan**: scene 1, title `Opening`, body `Welcome back. Today we start.`; scene 2, title `Tips`, body `Keep it simple. See you next time.`.

**Files.** `out/audio/001.wav` and `out/audio/002.wav`, valid WAVs, and `out/synth_record.json` with an entry for each scene. Each entry's `model` is an ElevenLabs model, so the pack is an ElevenLabs pack. Each entry's `sha256` equals the SHA-256 of the held WAV bytes (the `1` and `2` stand-ins below, as in the first example), and the joined `characters` of each entry equal the scene's body exactly. The full arrays are not shown; the mini-example in `## Record path` shows what they look like. Only the start times that are used appear here.

**Sentence starts.**

- Scene 1: `Welcome back.` begins at body offset 0, with alignment start time 0.24 seconds, which becomes 240. `Today we start.` begins at body offset 14, with alignment start time 1.2344 seconds, which becomes 1234.
- Scene 2: `Keep it simple.` begins at body offset 0, with alignment start time 0.12 seconds, which becomes 120. `See you next time.` begins at body offset 16, with alignment start time 1.5 seconds, which becomes 1500.

**Result.** `out/line_timings.json`, with the same keys and order as the first example and the same stand-in hashes:

```
{
  "scenes": [
    {
      "ordinal": 1,
      "sha256": "1111111111111111111111111111111111111111111111111111111111111111",
      "lines": [
        {
          "text": "Welcome back.",
          "start_ms": 240
        },
        {
          "text": "Today we start.",
          "start_ms": 1234
        }
      ]
    },
    {
      "ordinal": 2,
      "sha256": "2222222222222222222222222222222222222222222222222222222222222222",
      "lines": [
        {
          "text": "Keep it simple.",
          "start_ms": 120
        },
        {
          "text": "See you next time.",
          "start_ms": 1500
        }
      ]
    }
  ]
}
```

**stderr** (wording illustrative; stdout is empty):

```
scenevoice align: OK 2 scenes, 4 lines, 0 unmatched, 2 from synth record, 0 transcribed
```

Exit code 0. The run made no provider call, and needed no key.

Variant: if the joined `characters` of scene 2 differed from its body (for example, an audio tag was added), scene 2 would be transcribed: one call, one NOTE (`scenevoice align: NOTE scene 2: alignment text differs from plan body, transcribed`), and `OPENROUTER_API_KEY` would then be needed.
