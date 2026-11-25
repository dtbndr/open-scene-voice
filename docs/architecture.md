# SceneVoice architecture

SceneVoice is a local CLI, with a local web client in scope for release 2, for creators and editors. Hosted providers are used where the stages below call for them. See `SPEC.md` for the product boundary.

## Stages

The product is the Resolve timeline; the stages below build it in order.

- `scenevoice plan`: parses the creator script into the plan.
- `scenevoice beats`: an optional step after the script is saved, outside the chained flow. One hosted OpenRouter chat call splits each scene of the script into visual beats and writes them to a sidecar JSON file that is not part of the script, the plan, the pack or the timeline. It never overwrites a file. A reply that fails the checks or is cut off is still saved as raw text and the command exits 1, so a saved file counts as beats only after the shape check. Stdout stays empty, except that when the file cannot be written after the paid reply came back, it prints the reply on stdout so it is not lost.
- `scenevoice synth`: one WAV per scene in `DIR/audio` from the plan.
- `scenevoice align`: reads the plan and `DIR/audio`, takes line start times from the alignment kept in `DIR/synth_record.json` where the [align contract](specs/align-contract.md) allows it, and otherwise transcribes the scene with one hosted OpenRouter call; it writes `DIR/line_timings.json`. The line markers in the timeline rest on it; where it is absent or stale the timeline has scene markers only.
- `scenevoice pack`: with `--editor resolve` writes `resolve_timeline.otio` (the audio linked, the pauses, scene markers, and line markers where `line_timings.json` is fresh); always writes `scene_manifest.csv`, the fallback for editors the timeline does not cover.
- `scenevoice run`: chains the other stages and is not a separate behavior path. **Not built.** The operator chains `plan`, `synth`, `align` and `pack` by hand.

## Web client

Release 2 adds a local web client. A local server runs `plan`, `synth`, `align`, `pack` and `beats` as subprocesses, reports progress from a machine-readable stream, and cancels a run by ending the process. The CLI remains the only contract: new capabilities arrive as CLI commands first, and planning a script's visual beats arrives that way. Keys are stored per user and never served to the browser. The web server is built (`scenevoice web`); the browser interface is Milestone 13.

The stream is the `--progress json` flag on `plan`, `synth`, `align`, `pack` and `beats`: one JSON object per stderr line, for example `{"command":"synth","event":"scene","message":"scene 2/5 written to audio/002.wav","state":"done","scene":2,"total":5,"path":"audio/002.wav"}`. Every event carries `command`, `event` and `message`, and `event` is one of `scene`, `note`, `ok` or `fail`. A `scene` event adds `state` (`started` or `done`), `scene` and `total`, and a `done` from `synth` also adds `path`. A `fail` event adds `kind`, `scene`, `line` and `status`, and `kind` is one of `missing_key`, `bad_key`, `quota`, `provider_down`, `invalid_input` or `other`. The default, `--progress text`, is unchanged. Stderr lines that are not JSON, such as argparse errors and tracebacks, stay raw text, so a reader treats a line that does not parse as text. Cancelling is killing the process. For `align`, `done` means the scene is aligned in memory, not saved; a later write failure still ends in `fail` with kind `other`. The tests are the authority: `tests/progress/` and `tests/cli/test_cli_progress_flag.py`.

### The web server

`scenevoice web [--port N] [--no-open]` (code in `src/scenevoice/web/`, one function per file) is the server; each route calls the CLI as a subprocess and holds no business rules of its own. The tests in `tests/web/` are the authority for every rule below and win on conflict; a behaviour change ships with its test.

**Launch and perimeter.** It binds `127.0.0.1` only, on the fixed port 47615 unless `--port` (1024 to 65535) says otherwise, with `SO_REUSEADDR` and never `SO_REUSEPORT`; a busy port ends the command with a plain message and exit 1. It binds before it prints the link or opens a browser, so a program squatting on the port never sees the token. A random token is made per launch and delivered once in `http://127.0.0.1:PORT/?token=TOKEN`; redeeming it is a 303 that sets the session cookie `scenevoice_PORT` (`HttpOnly`, `SameSite=Lax`, no `Secure`, no expiry). Without a valid cookie or a redeemable link every request is 401 (`stale_link` under `/api/`, otherwise a fixed HTML page telling the creator to start `scenevoice web` again). `Host` must be exactly `127.0.0.1:PORT` (else 403 `bad_host`); every request that is not GET or HEAD needs `Origin: http://127.0.0.1:PORT` (else 403 `bad_origin`). No CORS header is sent and `OPTIONS` is 405. GET and HEAD never change state. Checks run in one order: duplicate headers, Host, Origin, authentication, route or static lookup, then body framing and JSON. Tests: `test_bind_socket.py`, `test_loopback_only.py`, `test_authenticate.py`, `test_auth_wiring.py`, `test_check_host.py`, `test_check_origin.py`, `test_dispatch.py`, `test_stale_response.py`.

Every child CLI run starts in an empty per-launch directory with the five key variables removed from its environment and `SCENEVOICE_KEYS_FILE` made absolute: under `web` only the per-user key file is used (`GET /api/keys` reports `ignored_environment`, names only). The workspace holds one folder per project: `~/Documents/SceneVoice`, or the absolute `SCENEVOICE_WORKSPACE`; the key file cannot live inside it. Tests: `test_child_env.py`, `test_resolve_workspace.py`, `test_key_file_overlap.py`, `test_run_web_workspace.py`.

**Shared rules.**

- Request bodies: GET, HEAD and DELETE take none; no `Transfer-Encoding`; one numeric `Content-Length` (required on POST and PUT); `application/json` (else 415); at most 64 KiB (else 413); invalid framing, UTF-8, JSON or a lone surrogate is 400. A wrong or missing field is 400 `bad_request`, decided before the project is looked up. Test: `test_read_json_body.py`.
- Every JSON error is `{"error": {"kind", "message"}}` with plain words and never a path or exception text. Test: `test_error_envelope.py`.
- Responses speak HTTP/1.0 with `Connection: close` and an exact `Content-Length`, except the event stream, which ends by closing. Every response carries `Referrer-Policy`, `X-Content-Type-Options`, `X-Frame-Options` and a `frame-ancestors` CSP; API responses add `Cache-Control: no-store`. The server prints nothing and no response, log line or exception holds a key value. Tests: `test_write_response.py`, `test_make_handler.py`, `test_security_headers.py`, `test_keys_redaction.py`.
- Static files come from a fixed set read at startup (no path is joined onto the disk); an unknown path without an extension serves `index.html`, never under `/api/`. Tests: `test_build_allowlist.py`, `test_serve_static.py`, `test_static_wiring.py`.
- Project ids: the raw path must match `[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?`, name a byte-exact real directory of the workspace, and a miss is 404 `not_found`. Only `script.md`, `beats.json`, `audio/NNN.wav`, `scene_manifest.csv` and `resolve_timeline.otio` are read or served, and each must be regular, exactly spelled, singly linked and not the key file; `.write-*.tmp` names never are. Tests: `test_project_id.py`, `test_project_dir.py`, `test_regular_file.py`, `test_audio_file_name.py`.
- Error kinds: `stale_link` 401; `bad_host`, `bad_origin` 403; `not_found` 404; `method_not_allowed` 405 (with `Allow`); `bad_request` 400, 413, 415, 416; `busy` 409 (a job holds the slot, a download is being prepared, or the server is stopping); `changed` 409 (the script or settings differ from what the creator confirmed); `not_allowed` 409 (the project is not in a state that allows the step); `unsupported` 501; `cli_failed` 502; `internal_error` 500.

**Routes.**

| Method and path | What it does |
| --- | --- |
| `GET /api/keys`, `PUT` and `DELETE /api/keys/{NAME}` | `keys status`, `keys set`, `keys remove`; one lock serialises the two writes; the value only ever travels on the child's stdin. |
| `GET`, `POST /api/projects` | List projects (newest first); make a project folder from a name. |
| `GET /api/projects/{id}` | The project detail read from disk: script revision, scenes, characters, per-step availability and `can` flags, `kept_backups`; it runs `plan` once on the saved script. |
| `GET`, `PUT /api/projects/{id}/script` | Read or replace `script.md` byte for byte (refused 409 `busy` while any job runs). |
| `GET /api/projects/{id}/beats` | `beats.json` as parsed JSON, only when it passes the light shape check (404 `not_found` when absent; plain 400 when unreadable, refused or not strict JSON); never says fresh or stale. |
| `POST /api/projects/{id}/check` | Run `plan` on the editor's text without saving; `{"ok": true, "scenes": N}` or one problem with its line. |
| `GET /api/projects/{id}/audio/{file}` | One allowlisted `NNN.wav` with a single `Range`; the name allowlist is checked before any disk call. |
| `GET /api/projects/{id}/pack.zip` | The allowlisted pack files as one in-memory zip (refused 409 `busy` while a job runs; 404 until packed; 413 above 1 GiB). |
| `POST /api/projects/{id}/reveal` | Open the folder in the file manager (macOS and Linux; the one route that starts a program). |
| `POST /api/projects/{id}/jobs` | Start one job; 202 with the current-job JSON. |
| `GET /api/jobs/current` | The current or last job. |
| `GET /api/jobs/current/events` | The job's events as server-sent events. |
| `POST /api/jobs/current/cancel` | Cancel the running job. |

Tests: `test_keys_routes.py`, `test_projects_routes.py`, `test_get_project_detail.py`, `test_put_script.py`, `test_check_script.py`, `test_serve_audio.py`, `test_build_pack_zip.py`, `test_get_pack_zip.py`, `test_post_reveal.py`, `test_post_job*.py`, `test_job_routes.py`, `test_projects_wiring.py`.

**Jobs.** The kinds are `synth` (modes `all`, `rest`, `restart`), `synth-scene`, `align`, `pack`, `beats` and `beats-redo`.

- One job at a time per server, in every project. A start first reserves the slot (409 `busy` if a job holds it or a download is being prepared), and only then reads `script.md`, runs `plan` once and counts. The counted plan bytes are written to a private file that the child reads, so what is voiced is what was counted. A paid start must echo the numbers it was shown (`scenes`, `characters`, `model` and the SHA-256 `revision` of the script; align echoes scenes and revision); the server compares them and answers 409 `changed` on any difference, and nothing on disk changes before every check has passed. Tests: `test_post_job.py`, `test_job_echo.py`, `test_job_availability.py`.
- The child runs in its own session. The runner drains stdout and stderr, turns `--progress json` lines into events and tracks `starting`, `running`, `cancelling` and the final `done`, `failed` or `cancelled`. The slot stays held until the end hooks (rollback, discard, swap) have run, so the next start never sees a half-finished one. Tests: `test_job_runner_run.py`, `test_job_runner_slot.py`, `test_job_runner_hooks.py`.
- Events are server-sent events with ids `<jobnumber>-<seq>`; `Last-Event-ID` replays what was missed. The stream ends with an `end` event and a reconnect after it gets 204, so a client closes on `end`. Tests: `test_job_events.py`, `test_stream_wiring.py`, `test_write_stream.py`.
- Cancel stops the child's whole process group (SIGINT, then a kill after a short delay) and the job ends `cancelled` after the child has exited; a cancelled run may still have been charged. Cancel on a reserved slot marks it refused: the start answers 409 `busy` "Cancelled before it started. Nothing was spent." Test: `test_job_runner_cancel.py`.
- Shutdown order: SIGINT, SIGTERM and SIGHUP (Control-C, closing the Terminal window, `kill`) all take the same path and are latched for the whole cleanup, so a second signal cannot abort it. The runner refuses new starts, cancels the current job, waits (bounded) for reserved slots and downloads to be released and for the child and its hooks to finish, then the server closes and the launch directory is removed. The "SceneVoice has stopped." line is printed afterwards and a hung-up terminal cannot stop it. A hard kill cannot be handled: one child may finish its paid call, and a relaunch reads the disk. This replaces the old rule that Control-C simply stops the server. Test: `test_run_web_shutdown.py` (a real process).
- Start again (`synth` mode `restart`) renames the allowlisted old files aside (`audio/NNN.wav`, `synth_record.json`, `line_timings.json`, pack outputs; nothing else is touched) before running. The first scene that finishes commits the run and discards the set-aside files; a run that ends before any scene finished restores them. If the restore fails they stay in the project folder as `.write-restart-*` files and the job fails with a message saying so; a failed unlink after a good restore is a `notice` and `kept_backups` is true. Tests: `test_restart_hook.py`, `test_set_aside_files.py`, `test_scan_backups.py`.
- Voice the rest (`mode` `rest`) runs one child per missing scene over the one counted plan. Pack deletes the old manifest and timeline before it runs, so a failed or cancelled pack leaves them gone. Align and pack need every scene voiced. Tests: `test_rest_runs.py`, `test_post_job_align_pack.py`, `test_delete_pack_outputs.py`.
- Beats and Redo beats run `beats` into a candidate file in the project folder (`.write-beats-<hex>.tmp`). Only a finished job whose candidate passes the shape check and names the confirmed script's SHA-256 is swapped in: a redo `os.replace`s `beats.json`, a first run links the candidate to it without following a symlink and never overwrites a `beats.json` made meanwhile. The candidate is deleted in every outcome (a reply the CLI rejected is deleted, the old set stays), and a leftover one is swept at the next beats start, before the redo plain-file check. Tests: `test_get_beats.py`, `test_post_job_beats.py`, `test_beats_hook.py`, `test_swap_beats.py`, `test_sweep_candidates.py`.
- Busy refusals: while any job holds the slot (reserved, running, cancelling or in its hooks), a script PUT and the zip download answer 409 `busy` in the words of the running kind ("SceneVoice is busy voicing." and so on). The PUT checks under the same script lock a start holds while it reads `script.md`, so a save either lands before the start's read or is refused. A download takes a zip admission around its assembly, released as soon as the bytes are in memory; downloads and saves coexist, and only a start is refused while a download is assembling (409 `busy` "SceneVoice is busy preparing a download."; nothing queues). Tests: `test_put_script.py`, `test_get_pack_zip.py`, `test_zip_admission.py`, `test_zip_guard.py`, `test_jobs_align_pack_wiring.py`.

### The web UI

The browser side is the SvelteKit project in `ui/`, built as a static single-page app into the directory the stdlib server serves (see "Static files" above). It only calls the routes above; what it shows and which buttons work comes from the server's answer (`can` flags and per-step state), not from its own copy of the rules. What a creator sees is in `docs/ux/release-2-web-client.md`; this section is the code map.

- **Pages** under `ui/src/routes/`: keys, projects, the project page (script editor), `beats`, `voice`, `review` and `pack`.
- **Controllers.** Each page has one controller in `ui/src/lib/<area>/` (for example `pack/controller.svelte.ts`, `PackController`) that owns its state and calls `ui/src/lib/api/`; components render it. Pure rules, failure wording and job handling sit beside it in plain `.ts` files.
- **`HeldRun`** (`ui/src/lib/jobs/held-run.svelte.ts`): a page holds the run it started or adopted, and Cancel names that run's id.
- **Job store** (`ui/src/lib/jobs/store.svelte.ts`): follows the one current job by polling and by server-sent events. The run-id rule: a status or event for a run other than the one a page holds is ignored, and the `end` event carries the run id so a page can tell its own run ended.
- **Free echo.** A free line-marker update (every scene from ElevenLabs) skips the dialog but still sends the confirmation echo with `scenes: 0` and the script revision.
- **Tests.** The only UI gate is the three tables `ui/tests/confirm-body.test.ts`, `job-store.test.ts` and `key-handling.test.ts`; do not add more UI tests.
- **Dev stub.** `node ui/scripts/dev.mjs` runs `scripts/dev_web_server.py` with stand-ins for `beats`, `synth` and `align` (scenario files under `ui/.dev/`; `scripts/dev_align_stub.py` has the scenarios ok, slow, fail and hold) and the real `keys`, `plan` and `pack`. `--real` runs the real CLI and can spend quota, so never use it in tests.

## Handoff

Stages pass UTF-8 JSON artifacts, read from a local path or stdin and written to stdout. Audio goes to an explicit local directory. The operator keeps intermediate artifacts by hand. `beats` sits outside this stdout JSON handoff: it writes a sidecar file, not read by any later stage, and leaves stdout empty, except that when the file cannot be written after the paid reply came back, it prints the reply on stdout so it is not lost.

## Plan

The plan is the authoritative scene snapshot: `synth` works from it alone and does not look back at the creator script. Original creator text is never silently rewritten.

## Live calls

Offline or fake work is kept separate from the explicit live paths: `synth` is a live (hosted, quota-spending) call, and so are `beats` and `align` where it transcribes (see the align contract). Live calls cost quota, so tests and debugging use fixtures.
