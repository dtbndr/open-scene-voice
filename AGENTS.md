# SceneVoice CLI

Concise guardrails for working in this repo; see `SPEC.md` for the product boundary.

## Setup

```bash
mise install                     # once: Python 3.12 + .venv; mise auto-activates the venv on cd
uv pip install -r requirements.txt  # once; the .venv is a uv venv with no pip (bare pip is the global Python: never use it)
```

In a non-interactive shell (no mise activation) run Python as `.venv/bin/python ...`.

Lint and typecheck (both must stay clean; mypy covers `src/` only):

```bash
.venv/bin/ruff check src tests
.venv/bin/mypy
```

## Operating rules

- Python 3.12, pinned in `mise.toml`; the venv lives in `.venv/`. Never install packages into the system Python. `ffmpeg` is a system dependency; do not vendor it.
- Secrets live in `.env`. Never commit `.env`; keep `.env.example` current.
- **Hosted TTS calls cost quota.** Never call a provider API in tests or while debugging unrelated code; use fixtures.
- Keep the product small: support the CLI and the local web client; avoid features and formats that no editor has asked for.

## Terminology and priorities

- `P0`-`P3` are reserved exclusively for priority/severity grades.
- Never use `P` as a phase prefix. Write `Phase 1, Milestone 3, Workstream 1` in prose and `Phase1-M3-WS1` as a compact identifier.

## Contract lifecycle

- Maintainers review the product boundary and the user experience, not CLI contracts; tests are the authority for CLI behaviour.
- Each `docs/specs/` file is non-authoritative. Delete a spec when a change next touches the behaviour it describes; the reviewer checks every rule is pinned by a test or dropped on purpose.
- Contract changes ship in the same change and commit as the code, not in docs-only changes.
- Provider facts (response and error bodies) become recorded fixtures with an observed date. Rationale lives in test names, docstrings and comments.
- Maintainer sign-off is needed only for `SPEC.md`, the user-facing flow and screens, quota and cost behaviour, and security posture.
- Backward compatibility is not a concern; list changes in the release notes.
- `docs/script-format.md` is the one user-facing script guide.
