# SceneVoice architecture

SceneVoice is a local CLI for technically comfortable creators and editors. Hosted providers are used where the stages below call for them. See `SPEC.md` for the product boundary.

## Stages

The product is the Resolve timeline; the stages below build it in order.

- `scenevoice plan`: parses the creator script into the plan.
- `scenevoice synth`: one WAV per scene in `DIR/audio` from the plan.
- `scenevoice align`: reads the plan and `DIR/audio`, takes line start times from the alignment kept in `DIR/synth_record.json` where the [align contract](specs/align-contract.md) allows it, and otherwise transcribes the scene with one hosted OpenRouter call; it writes `DIR/line_timings.json`. The line markers in the timeline rest on it; where it is absent or stale the timeline has scene markers only.
- `scenevoice pack`: with `--editor resolve` writes `resolve_timeline.otio` (the audio linked, the pauses, scene markers, and line markers where `line_timings.json` is fresh); always writes `scene_manifest.csv`, the fallback for editors the timeline does not cover.
- `scenevoice run`: chains the other stages and is not a separate behavior path. **Not built.** The operator chains `plan`, `synth`, `align` and `pack` by hand.

## Handoff

Stages pass UTF-8 JSON artifacts, read from a local path or stdin and written to stdout. Audio goes to an explicit local directory. The operator keeps intermediate artifacts by hand.

## Plan

The plan is the authoritative scene snapshot: `synth` works from it alone and does not look back at the creator script. Original creator text is never silently rewritten.

## Live calls

Offline or fake work is kept separate from the explicit live paths: `synth` is a live (hosted, quota-spending) call, and so is `align` where it transcribes (see the align contract). Live calls cost quota, so tests and debugging use fixtures.
