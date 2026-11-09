# Plan contract

**Status: Approved 2026-10-01 by the owner.**

This contract defines plan semantics. It builds on `docs/specs/script-contract.md` and does not authorize implementation, workspace creation, provider calls, or a pilot. It defines no error code or CLI behavior.

## Creating a plan

A plan is derived only from file-backed input whose complete contents are a valid source under the [creator script contract](script-contract.md). The input is read as supplied: planning does not normalize, trim, render, or rewrite source text.

An invalid script is rejected and yields no partial plan. A missing or unreadable input is a separate operational failure and also yields no partial plan.

## Scenes

The plan carries one scene per recognized marker, in source order. Each scene carries exactly its one-based ordinal, title, and body, with title and body verbatim. No preamble or other source text is carried as a scene field.

## Snapshot

The plan is the authoritative scene snapshot for synthesis. `synth` uses the plan alone: it does not read, look up, or validate against the original script, and editing, moving, or deleting the script does not change the plan.

## Serialization

A plan is serialized as a single UTF-8 JSON document: an object whose only key is `scenes`. The value of `scenes` is an array of scene objects in source order. It holds at least one scene, because a valid script has at least one marker and an invalid script yields no plan.

Each scene object has exactly these keys:

- `ordinal`: an integer, one-based, taken from the scene's position and not from the title text. `Scene 6:` after `Scene 4:` has ordinal 5.
- `title`: a string.
- `body`: a string.

The scene object has no other keys, and the plan object has no other keys.

Title and body are verbatim: the parsed `title` and `body` values equal the source text exactly. The only escapes used are those JSON requires (`\"`, `\\`, and `\n` for LF). Printable non-ASCII text is written as itself and is never written as a `\uXXXX` escape. This is a writer-side rule, checked against the raw output text and not against parsed values.

Key order, whitespace between tokens, and a trailing newline are not significant.

Illustrative example (not a normative layout):

```json
{"scenes": [
  {"ordinal": 1, "title": "Arrival", "body": "The café opens at dawn.\n"}
]}
```
