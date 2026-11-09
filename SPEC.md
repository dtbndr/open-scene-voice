# SceneVoice product boundary

The `audio/` folder layout and the optional Resolve timeline below were reopened on 2026-10-07. The `audio/` folder layout (WS22) and the `pack --editor resolve` timeline with scene markers (WS23) are implemented; the line markers, check 4a and the `NOTE` lines are implemented in WS25, and `scenevoice align` is built in WS25 (offline) and was live-accepted in WS26 (2026-10-09, with a real key and in DaVinci Resolve 21.1.1); its record path (check 5a, start times from `DIR/synth_record.json` for ElevenLabs scenes) is built in WS32 and was accepted offline on the R2 pack. The contracts are `docs/specs/pack-contract.md`, `docs/specs/synth-contract.md` and `docs/specs/align-contract.md`.

## Product direction

SceneVoice is open source for self-use by technically comfortable video creators and editors, alongside the done-for-you Voice Your Scenes service.

## Output

A scene-marked creator script becomes a pack folder (`DIR`) holding:

- `resolve_timeline.otio`, a DaVinci Resolve timeline with the scene audio linked, the pauses between clips and scene and line markers already placed, so an editor imports it in one step (written by `pack --editor resolve`);
- ordered per-scene WAVs in an `audio/` folder, which the timeline links to;
- `scene_manifest.csv`, for editors the timeline does not cover.

The timeline is the product; the WAVs and the manifest are what it is built from and the fallback for other editors. Without `--editor resolve` the pack is the WAVs plus the manifest. The line markers rest on line timings that `scenevoice align [PLAN] DIR` writes to `DIR` beforehand (it has no language option; the contract is `docs/specs/align-contract.md`); `pack` itself never calls `align`.

### `scene_manifest.csv`

One header row, then one row per scene in script order. It gives an editor without a supported timeline (Final Cut Pro, Premiere Pro, and similar) what they need to place the clips by hand.

| Column | Meaning |
| --- | --- |
| `scene` | 1-based scene number, in script order |
| `label` | Scene label as written in the creator script |
| `file` | WAV path, `audio/NNN.wav`, relative to the pack folder |
| `duration_s` | Clip length in seconds, 3 decimal places |

## Provider

The default provider is Vertex AI `gemini-3.8-flash-tts` (the earlier `gemini-3.1-flash-tts-preview` was superseded in M4) with the 30 prebuilt Gemini TTS voices and a required `--model` choice among the four models of the synth contract (`synth --voice`, `synth --model`; the contract is `docs/specs/synth-contract.md`). The TTS provider is inferred from `--model`: the two Gemini models (`gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts`) use Vertex, and `eleven_flash_v2_5` and `eleven_v4` use ElevenLabs with a BYOK key; there is no `--provider` flag and no default model (see the synth contract). Each script, hence each pack, is voiced by one provider, chosen for the script, and `synth --scene N` uses the same provider; mixed-provider packs are unsupported. OpenRouter `openai/whisper-large-v3-turbo` is used by `align` only, where the align contract routes a scene to transcription (the contract is `docs/specs/align-contract.md`).

## Out of scope

- Inherited normalization, limiting, de-essing, defect flags, reports, and self-checks
- Master WAV, generic marker CSV, EDL, and FCPXML
- Timelines for any editor other than Resolve
- Legacy compatibility
- A provider or voice marketplace
- Broad pronunciation guarantees
- A production-permanence promise for the Preview model
