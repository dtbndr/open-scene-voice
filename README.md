# SceneVoice

A local CLI that turns a scene-marked creator script into a DaVinci Resolve timeline with the voiceover linked, scene and line markers set, and a `scene_manifest.csv` for editors we do not support. Intended for technically comfortable creators and editors to use themselves, it also supports the done-for-you [Voice Your Scenes](https://voiceyourscenes.com) service. The product boundary is in [`SPEC.md`](SPEC.md).

## Usage

Four commands, run in order. Keep the plan file: `synth`, `align` and `pack` all read it.

```bash
scenevoice plan sample/scripts/short.md > plan.json
scenevoice synth plan.json --out out --voice Charon --model gemini-3.8-flash-lite-tts
scenevoice align plan.json out
scenevoice pack plan.json out --editor resolve
```

The result in `out/` is a DaVinci Resolve timeline (`resolve_timeline.otio`) with the scene audio linked, scene markers and line markers, ready to import in one step, plus `scene_manifest.csv` for editors we do not support.

`synth` makes hosted text-to-speech calls and `align` may make hosted transcription calls; each needs credentials, and uses provider quota, where it calls. Run `scenevoice <command> --help` for all options. What `pack` writes and where, and what `--editor` adds, is in the [pack contract](docs/specs/pack-contract.md); `align` is in the [align contract](docs/specs/align-contract.md). To redo one scene, see [Single-scene regeneration](docs/specs/synth-contract.md#single-scene-regeneration).

## More

- Setup, lint and typecheck, and contributor and agent rules: [`CLAUDE.md`](CLAUDE.md)
- How the stages fit together: [`docs/architecture.md`](docs/architecture.md)

## Contributing

Contributions are welcome. Open an issue, start a discussion, or send a pull request. A bot will ask you to sign the [Contributor License Agreement](CLA.md) on your first pull request; nothing is merged until it is signed.

## License and names

The code is licensed under the [GNU AGPL-3.0-only](LICENSE). "SceneVoice" and "Voice Your Scenes" are marks of Abhishek Mukherjee; the licence covers the code only and grants no rights to those names.
