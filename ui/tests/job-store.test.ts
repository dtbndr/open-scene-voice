// Job-store table (U17), three rows, run against the pure reducer and JobStore with fakes (no components).
import { describe, expect, it, vi } from 'vitest';
import { emptyView, reduce } from '../src/lib/jobs/reduce';
import { JobStore, type EventSourceLike } from '../src/lib/jobs/store.svelte';
import type { CurrentJob, JobEvent, JobFailure, JobState } from '../src/lib/api/types';
import { ApiError, NetworkError } from '../src/lib/api/errors';
import { acceptedRun, heldRun, ownership } from '../src/lib/voice/guard';
import { chooseKind, settleMode } from '../src/lib/voice/flow';
import { providerName, tryAgainMode, voiceFailureView } from '../src/lib/voice/failure';
import { cancelledText, offeredModes, runModelFor, sceneSets } from '../src/lib/voice/cancelled';
import { redoState, replaceLine, sceneNotes, settingsLine, stepScene } from '../src/lib/voice/review';
import { alignFailureView, canDownload, needsOpenRouterKey, updatePlan } from '../src/lib/pack/rules';
import type { ProjectDetail } from '../src/lib/api/types';
import { PackController, type PackDeps } from '../src/lib/pack/controller.svelte';
import { CANCEL_MISMATCH_WORDS, ENDED_WORDS, cancelAnswer, resolveEnd } from '../src/lib/voice/job-end';

function job(state: JobState, scenesDone: number, project = 'p'): CurrentJob {
  return {
    state,
    job: {
      kind: 'synth',
      mode: 'all',
      project,
      scene: null,
      started: state !== 'starting',
      finished: ['done', 'failed', 'cancelled'].includes(state),
      completed: state === 'done',
      total: 3,
      scenes_done: scenesDone,
      failure: null,
      notice: null,
      run: '0'.repeat(32)
    }
  };
}
const snapshot = (current: CurrentJob): JobEvent => ({ type: 'state', seq: 1, ...current });
const end = (current: CurrentJob, seq: number): JobEvent => ({ type: 'end', seq, ...current });
const scene = (seq: number, state: 'started' | 'done', number: number): JobEvent => ({
  type: 'scene',
  seq,
  command: 'synth',
  message: `scene ${number}`,
  state,
  scene: number,
  total: 3
});

class FakeSource implements EventSourceLike {
  readyState = 1;
  closed = false;
  onmessage: ((event: { data: string; lastEventId: string }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  close(): void {
    this.closed = true;
    this.readyState = 2;
  }
  emit(id: string, event: JobEvent): void {
    this.onmessage?.({ data: JSON.stringify(event), lastEventId: id });
  }
}

const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

function harness() {
  const sources: FakeSource[] = [];
  const state = { current: job('running', 0), endCalls: [] as (string | null)[], release: () => {} };
  const store = new JobStore({
    fetchJob: async () => state.current,
    createSource: () => {
      const source = new FakeSource();
      sources.push(source);
      return source;
    },
    onEnd: (project) => {
      state.endCalls.push(project);
      return new Promise<void>((resolve) => {
        state.release = resolve;
      });
    }
  });
  return { store, sources, state };
}

describe('job store', () => {
  // P1 (scenes the creator can rely on after a stop): a failed end and a cancelled end both keep the finished scenes.
  it.each<JobState>(['failed', 'cancelled'])('P1 a %s end leaves the done scenes as kept', (final) => {
    let view = reduce(emptyView, snapshot(job('running', 0)), 0);
    view = reduce(view, scene(1, 'started', 1), 7);
    view = reduce(view, scene(2, 'done', 1), 7);
    view = reduce(view, scene(3, 'started', 2), 7);
    view = reduce(view, scene(4, 'done', 2), 7);
    view = reduce(view, scene(5, 'started', 3), 7);
    view = reduce(view, end(job(final, 2), 6), 7);
    expect(view.scenes).toEqual({ 1: 'kept', 2: 'kept' });
    expect(view.current.job?.scenes_done).toBe(2);
  });

  // P1: the same event twice, and a whole replay on a new stream (fresh 0-1 snapshot first), change nothing.
  it('P1 a repeated scene event and a full replay leave the scene map and counts unchanged', () => {
    const run: [JobEvent, number][] = [
      [snapshot(job('running', 1)), 0],
      [scene(1, 'started', 1), 7],
      [scene(2, 'done', 1), 7],
      [scene(3, 'started', 2), 7]
    ];
    let view = emptyView;
    for (const [event, id] of run) view = reduce(view, event, id);
    const before = { scenes: { ...view.scenes }, done: view.current.job?.scenes_done, total: view.current.job?.total };
    view = reduce(view, scene(2, 'done', 1), 7);
    for (const [event, id] of run) view = reduce(view, event, id);
    expect({ scenes: { ...view.scenes }, done: view.current.job?.scenes_done, total: view.current.job?.total }).toEqual(before);
    expect(before.scenes).toEqual({ 1: 'done', 2: 'started' });
  });

  // P1 (the page must re-read the project once a job ends, by `end` or by a poll, never twice, and never close early).
  it('P1 end re-reads once, settled waits for the re-read, and the stream closes only after it', async () => {
    const { store, sources, state } = harness();
    await store.refresh();
    const source = sources[0];
    source.emit('0-1', snapshot(job('running', 0)));
    source.emit('1-1', scene(1, 'done', 1));
    state.current = job('done', 3);
    source.emit('1-2', end(job('done', 3), 2));
    await flush();
    expect(state.endCalls).toEqual(['p']);
    expect(store.settled).toBe(false);
    expect(source.closed).toBe(false);
    state.release();
    await flush();
    expect(store.settled).toBe(true);
    expect(source.closed).toBe(true);
  });

  it('P1 a poll that sees the job finished with no end (snapshot-only stream) re-reads once; a late end adds none', async () => {
    const { store, sources, state } = harness();
    await store.refresh();
    sources[0].emit('0-1', snapshot(job('running', 0)));
    state.current = job('failed', 0);
    await store.refresh();
    await flush();
    expect(state.endCalls).toEqual(['p']);
    expect(store.settled).toBe(false);
    await store.refresh();
    sources[0].emit('2-2', end(job('failed', 0), 2));
    await flush();
    expect(state.endCalls).toEqual(['p']);
    state.release();
    await flush();
    expect(store.settled).toBe(true);
  });

  // P1 (paid-run state): a live-to-live replacement of the same kind and project is a new run, so a new generation with a clean view.
  it('P1 a different run of the same kind and project bumps generation and resets the view; the store settles nothing', async () => {
    const { store, sources, state } = harness();
    await store.refresh();
    sources[0].emit('0-1', snapshot(job('running', 0)));
    sources[0].emit('1-1', scene(1, 'done', 1));
    const before = store.generation;
    expect(store.view.scenes).toEqual({ 1: 'done' });
    const replacement = job('running', 0);
    replacement.job!.run = '1'.repeat(32);
    state.current = replacement;
    await store.refresh();
    expect(store.generation).toBe(before + 1);
    expect(store.view.scenes).toEqual({});
    expect(state.endCalls).toEqual([]);
    expect(store.settled).toBe(true);
    await store.refresh(); // the same run again is not a new generation
    expect(store.generation).toBe(before + 1);
  });

  // P1 (quota: a page must not adopt or stop another project's or another kind's paid run): the guard is the adoption authority.
  describe('foreign-job guard', () => {
    const OWN = ['synth', 'synth-scene'] as const;
    const withKind = (kind: 'synth' | 'beats', project: string): CurrentJob => {
      const base = job('running', 0, project);
      return { ...base, job: { ...base.job!, kind } };
    };
    it.each([
      ['own: same project and an own kind', withKind('synth', 'p'), 'own'],
      ['foreign: another project', withKind('synth', 'q'), 'foreign'],
      ['foreign: same project, another kind', withKind('beats', 'p'), 'foreign'],
      ['none: no job', { state: 'idle', job: null } as CurrentJob, 'none']
    ] as const)('P1 %s', (_name, current, expected) => {
      expect(ownership(current.job, 'p', OWN)).toBe(expected);
    });

    it('P1 a held run is never replaced from the store; with none held only an own job is adopted; a start for another project sets nothing', () => {
      const mine = withKind('synth', 'p');
      const other = withKind('synth', 'q');
      expect(heldRun('A', other, 'p', OWN)).toBe('A');
      expect(heldRun('A', mine, 'p', OWN)).toBe('A'); // a same-kind replacement would pass as own
      expect(heldRun(null, other, 'p', OWN)).toBeNull();
      expect(heldRun(null, withKind('beats', 'p'), 'p', OWN)).toBeNull();
      expect(heldRun(null, mine, 'p', OWN)).toBe(mine.job!.run);
      expect(acceptedRun('p', 'q', mine)).toBeNull();
      expect(acceptedRun('p', 'p', mine)).toBe(mine.job!.run);
    });
  });

  // P1 (quota and never stuck running, decision 3): the page holds run A; any observation that is not A-live settles.
  describe('job-end rule', () => {
    const A = '0'.repeat(32);
    const B = '1'.repeat(32);
    const final = (state: JobState, run = A, failure: JobFailure | null = null): CurrentJob => {
      const base = job(state, 3);
      return { ...base, job: { ...base.job!, run, failure } };
    };
    const live = (run = A): CurrentJob => ({ ...job('running', 1), job: { ...job('running', 1).job!, run } });
    const failure: JobFailure = { kind: 'quota', message: 'out', scene: 2, status: 429 };
    const none: CurrentJob = { state: 'idle', job: null };
    const gone = new ApiError(404, 'not_found', 'gone');
    const lookupOf = (answer: CurrentJob | Error) => {
      const calls: string[] = [];
      return {
        calls,
        lookup: async (run: string) => {
          calls.push(run);
          if (answer instanceof Error) throw answer;
          return answer;
        }
      };
    };

    it.each([
      ['A live keeps running', live(), { settle: 'live' }],
      ['A done settles', final('done'), { settle: 'ended', outcome: 'done' }],
      ['A cancelled settles', final('cancelled'), { settle: 'ended', outcome: 'cancelled' }],
      ['A failed settles with its own failure', final('failed', A, failure), { settle: 'ended', outcome: 'failed', failure }]
    ] as const)('P1 seen %s with no lookup', async (_name, seen, expected) => {
      const { calls, lookup } = lookupOf(new Error('must not be called'));
      expect(await resolveEnd(A, seen, lookup)).toMatchObject(expected);
      expect(calls).toEqual([]);
    });

    it.each([
      ['no job, A still live', none, live(), { settle: 'live' }],
      ['another run seen, A final done', live(B), final('done'), { settle: 'ended', outcome: 'done' }],
      ['no job, A retained failed', none, final('failed', A, failure), { settle: 'ended', outcome: 'failed', failure }],
      ['no job, A evicted (404): generic ended', none, gone, { settle: 'ended', outcome: 'failed', failure: { kind: 'other', message: ENDED_WORDS } }],
      ['lookup network error waits for the next poll', live(B), new NetworkError(), { settle: 'wait' }],
      ['lookup 500 waits for the next poll', none, new ApiError(500, 'internal', 'x'), { settle: 'wait' }]
    ] as const)('P1 %s: exactly one lookup of A', async (_name, seen, answer, expected) => {
      const { calls, lookup } = lookupOf(answer);
      expect(await resolveEnd(A, seen, lookup)).toMatchObject(expected);
      expect(calls).toEqual([A]);
    });

    // P1 (a Cancel names a run): 409 changed and 404 not_found both mean "that run is not live now": look it up, no message
    // of their own for 404; only 409 gets the proposed mismatch words; any other failure shows its own words.
    it.each([
      ['409 changed', new ApiError(409, 'changed', 'x'), { lookup: true, notice: CANCEL_MISMATCH_WORDS }],
      ['404 not_found', new ApiError(404, 'not_found', 'x'), { lookup: true, notice: null }],
      ['anything else', new ApiError(500, 'internal', 'broke'), { lookup: false, notice: 'broke' }]
    ] as const)('P1 cancel answer %s', (_name, error, expected) => {
      expect(cancelAnswer(error)).toEqual(expected);
    });
  });
  // Voicing failure views: pure selection by kind and provider. The approved texts are pinned verbatim (not to be reworded).
  describe('voicing failure view', () => {
    const fail = (kind: JobFailure['kind'], message = '', status: number | null = null) => ({ kind, status, message });
    const GOOGLE_BAD_KEY =
      'Google Cloud did not accept your details. Check that you pasted all of the key, that the project ID and region are right, and that the account is active.';
    const EL_DOWN = 'ElevenLabs did not answer. Scenes already voiced are kept. Try again in a minute.';
    const EL_QUOTA =
      'Your ElevenLabs allowance is used up. Scenes already voiced are kept. Add credit or wait for your allowance to renew, then try again.';

    // P1 (approved wording and buttons per kind; not the beats wording): text verbatim, buttons exactly as approved.
    it.each([
      ['Google bad_key', fail('bad_key'), 'google', GOOGLE_BAD_KEY, ['checkDetails', 'tryAgain']],
      ['ElevenLabs provider_down', fail('provider_down'), 'elevenlabs', EL_DOWN, ['tryAgain', 'back']],
      ['ElevenLabs quota', fail('quota'), 'elevenlabs', EL_QUOTA, ['tryAgain']],
      ['Google provider_down fills the provider name', fail('provider_down'), 'google', EL_DOWN.replace('ElevenLabs', 'Google Cloud'), ['tryAgain', 'back']],
      ['Google quota fills the provider name', fail('quota'), 'google', EL_QUOTA.replace('ElevenLabs', 'Google Cloud'), ['tryAgain']]
    ] as const)('P1 %s', (_name, failure, provider, text, buttons) => {
      expect(voiceFailureView(failure, provider)).toEqual({ text, buttons });
    });

    // P1 (a failure never hides its reason): the CLI's own text (invalid_input) and a non-empty `other` message, such as the
    // 404 "ended" wording, show as plain text with Back only; an empty `other` gets generic words, never an empty alert.
    it.each([
      ['invalid_input shows the CLI text', fail('invalid_input', 'Scene 2 is empty.'), 'Scene 2 is empty.'],
      ['other with a message shows it', fail('other', ENDED_WORDS), ENDED_WORDS]
    ] as const)('P1 %s, Back only', (_name, failure, text) => {
      const view = voiceFailureView(failure, 'google');
      expect(view.text).toBe(text);
      expect(view.buttons).toEqual(['back']);
    });
    it('P1 other with no message still has words and Back', () => {
      const view = voiceFailureView(fail('other'), 'elevenlabs');
      expect(view.text).not.toBe('');
      expect(view.buttons).toEqual(['back']);
    });
    it('P1 ElevenLabs bad_key offers Check my details and Try again (proposed default)', () => {
      const view = voiceFailureView(fail('bad_key'), 'elevenlabs');
      expect(view.text).toContain('ElevenLabs');
      expect(view.buttons).toEqual(['checkDetails', 'tryAgain']);
    });

    // P1 (cost): Try again after a partial run voices only the rest; whole or single-scene reruns keep their mode.
    it.each([
      ['all with rest allowed becomes rest', 'all', true, 'rest'],
      ['restart with rest allowed becomes rest', 'restart', true, 'rest'],
      ['all with nothing voiced stays all', 'all', false, 'all'],
      ['rest stays rest', 'rest', true, 'rest']
    ] as const)('P1 try again mode: %s', (_name, mode, restAllowed, expected) => {
      expect(tryAgainMode({ synth: { all: true, rest: restAllowed, restart: true } } as never, mode)).toBe(expected);
    });

    // P1: paid flow blocked. After the key popup (retry false) a partly voiced project must still open its confirmation.
    it.each([
      ['partial run: all is unavailable, the rest opens', 'all', { all: false, rest: true, restart: true }, 'rest'],
      ['a creator\'s Start again is kept', 'restart', { all: false, rest: true, restart: true }, 'restart']
    ] as const)('P1: paid flow blocked, popup path: %s', (_name, mode, synth, expected) => {
      const detail = { script: { scenes: [{}, {}] }, audio: { scenes: [{ voiced: true }, { voiced: false }] }, can: { synth } } as never;
      const settled = settleMode(detail, mode, false);
      expect(chooseKind((detail as { can: never }).can, settled)).not.toBeNull();
      expect(settled).toBe(expected);
    });

    it.each([
      ['ElevenLabs key', { models: ['m'], env_names: ['ELEVENLABS_API_KEY'], voices: null }, 'elevenlabs'],
      ['Google details', { models: ['m'], env_names: ['GOOGLE_CLOUD_PROJECT'], voices: ['Leda'] }, 'google']
    ] as const)('P1 provider from the catalog entry: %s', (_name, spec, expected) => {
      expect(providerName(spec as never)).toBe(expected);
    });
  });
  describe('cancelled and partial states', () => {
    const nums = (...ordinals: number[]) => ordinals;
    // P1 (the cancelled page says which scenes finished and which did not): approved sentence for a contiguous set; the
    // single-scene and non-contiguous forms are proposed. One row per class.
    it.each([
      ['contiguous (approved)', nums(1, 2), nums(3, 4, 5, 6), 'Stopped. Scenes 1 and 2 are voiced and kept. Scenes 3 to 6 were not.'],
      ['one unvoiced scene', nums(1, 2), nums(3), 'Stopped. Scenes 1 and 2 are voiced and kept. Scene 3 was not.'],
      ['non-contiguous unvoiced', nums(1, 3, 4, 6), nums(2, 5), 'Stopped. Scenes 1, 3, 4 and 6 are voiced and kept. Scenes 2 and 5 were not.'],
      ['nothing voiced', nums(), nums(1, 2), 'Stopped. No scene is voiced yet.']
    ] as const)('P1 cancelled sentence: %s', (_name, voiced, unvoiced, text) => {
      expect(cancelledText(voiced, unvoiced)).toBe(text);
    });
    it('P1 the sets come from the detail read after the run, in script order', () => {
      const detail = {
        script: { scenes: [{ ordinal: 1 }, { ordinal: 2 }, { ordinal: 3 }] },
        audio: { scenes: [{ ordinal: 1, voiced: true }, { ordinal: 2, voiced: false }, { ordinal: 3, voiced: true }] }
      };
      expect(sceneSets(detail as never)).toEqual({ voiced: [1, 3], unvoiced: [2] });
    });
    // P0 (the page never derives availability; a paid start needs the server's can): an offer shows only when can allows it.
    it.each([
      ['both', { all: false, rest: true, restart: true }, ['rest', 'restart']],
      ['restart only', { all: false, rest: false, restart: true }, ['restart']],
      ['none', { all: false, rest: false, restart: false }, []]
    ] as const)('P0 offers follow can: %s', (_name, synth, expected) => {
      expect(offeredModes({ synth } as never)).toEqual(expected);
      expect(offeredModes(undefined)).toEqual([]);
    });
    // P1 (the missing-key popup names the right provider): after a resume the run's model is the record's, else the choice.
    it.each([
      ['recorded model wins', { model: 'eleven_v4' }, 'gemini-3.8-flash-tts', 'eleven_v4'],
      ['no record falls back', null, 'gemini-3.8-flash-tts', 'gemini-3.8-flash-tts']
    ] as const)('P1 run model on resume: %s', (_name, settings, fallback, expected) => {
      expect(runModelFor(settings, fallback)).toBe(expected);
    });
  });
  describe('review rules', () => {
    // P1 (never hide a scene; a plain note only for an explicit false): null means unvoiced or unrecorded, not mismatched.
    it.each([
      ['explicit false audio', { wav_matches_record: false, text_matches: null }, 1],
      ['explicit false text', { wav_matches_record: null, text_matches: false }, 1],
      ['both null (unvoiced or unrecorded)', { wav_matches_record: null, text_matches: null }, 0],
      ['both true', { wav_matches_record: true, text_matches: true }, 0]
    ] as const)('P1 scene notes: %s', (_name, entry, count) => {
      expect(sceneNotes(entry as never)).toHaveLength(count);
    });
    // P0 (a paid call needs the server's can and a free slot): Redo shows only when can.synth_scene; a foreign job greys it.
    it.each([
      ['not allowed', { synth_scene: false }, false, 'hidden'],
      ['not allowed and busy', { synth_scene: false }, true, 'hidden'],
      ['allowed, foreign job', { synth_scene: true }, true, 'busy'],
      ['allowed', { synth_scene: true }, false, 'ready']
    ] as const)('P0 redo state: %s', (_name, can, foreign, expected) => {
      expect(redoState(can as never, foreign)).toBe(expected);
      expect(redoState(undefined, false)).toBe('hidden');
    });
    // P1 (every scene stays reachable, none is skipped): Prev and Next step through the script's own scene numbers.
    it.each([
      ['next in the middle', [1, 2, 4], 2, 1, 4],
      ['previous in the middle', [1, 2, 4], 2, -1, 1],
      ['next at the end stops', [1, 2, 4], 4, 1, null],
      ['previous at the start stops', [1, 2, 4], 1, -1, null]
    ] as const)('P1 scene step: %s', (_name, ordinals, current, step, expected) => {
      expect(stepScene(ordinals, current, step)).toBe(expected);
    });
    // P0 (a paid redo is confirmed knowing it replaces the audio, with the recorded settings it will use).
    it('P0 the redo confirmation names the scene and shows the recorded settings read-only', () => {
      expect(replaceLine(2)).toBe('This replaces the current audio for scene 2.');
      expect(settingsLine({ voice: 'Leda', model: 'gemini-3.8-flash-tts' })).toBe('Voice: Leda, Gemini standard');
      expect(settingsLine({ voice: null, model: 'unknown-model' })).toBe('Voice: unknown-model');
    });
  });
  describe('pack rules', () => {
    const detail = (align: boolean, listen: number, manifest = true): ProjectDetail =>
      ({
        script: { revision: 'r', scenes: [], total_characters: 0 },
        can: { align },
        line_markers: { state: 'stale', stale_scenes: [], listen_scenes: listen },
        pack: { manifest, timeline: false }
      }) as unknown as ProjectDetail;
    // P0 (a paid update never skips the confirmation; a free one has none). Unavailable wins over free.
    it.each([
      ['unavailable even with nothing to listen to', detail(false, 0), 'unavailable'],
      ['free when nothing is listened to', detail(true, 0), 'free'],
      ['paid when scenes are listened to', detail(true, 3), 'paid'],
      ['paid when the count is missing', { ...detail(true, 0), line_markers: undefined }, 'paid']
    ] as const)('P0 update plan: %s', (_name, project, plan) => {
      expect(updatePlan(project)).toBe(plan);
    });
    // P1 (the OpenRouter popup only when something is listened to).
    it('P1 the key popup is needed only for a paid update', () => {
      expect(needsOpenRouterKey(detail(true, 2))).toBe(true);
      expect(needsOpenRouterKey(detail(true, 0))).toBe(false);
      expect(needsOpenRouterKey(detail(false, 2))).toBe(false);
    });
    // P1 (no dead end: a missing key opens the popup; a bad key offers the details).
    it('P1 align failure: missing key goes to the popup, bad key offers Check my details', () => {
      const failure = (kind: 'missing_key' | 'bad_key') => ({ kind, status: null, message: '', scene: null });
      expect(alignFailureView(failure('missing_key')).popup).toBe(true);
      const bad = alignFailureView(failure('bad_key'));
      expect(bad.popup === false && bad.buttons).toContain('checkDetails');
    });
    // P1 (a download is never offered when it would answer 409 JSON or the pack is absent).
    it('P1 download needs a pack and no active job', () => {
      expect(canDownload(detail(true, 0), false)).toBe(true);
      expect(canDownload(detail(true, 0), true)).toBe(false);
      expect(canDownload(detail(true, 0, false), false)).toBe(false);
      expect(canDownload({ script: detail(true, 0).script }, false)).toBe(false);
    });
  });
  // P0: paid call without confirm. The key-save callback (afterPopup) reopens the confirmation from a fresh read; only
  // the creator's own confirm() posts, so the start request count stays 0 until then. Fake client, no provider call.
  it('P0: paid call without confirm: afterPopup posts nothing until confirm()', async () => {
    const detail = {
      script: { revision: 'r', scenes: [] },
      can: { align: true },
      line_markers: { state: 'stale', stale_scenes: [2], listen_scenes: 1 }
    } as unknown as ProjectDetail;
    let saved = false;
    const startJob = vi.fn(async () => job('running', 0));
    const deps = {
      api: { project: async () => detail, keys: async () => ({ keys: { OPENROUTER_API_KEY: { saved } } }), startJob },
      jobs: { active: false, view: emptyView, counts: null, refresh: async () => job('idle', 0), listen: () => () => undefined }
    } as unknown as PackDeps;
    const ctl = new PackController(() => 'p', deps);
    await ctl.update();
    expect(ctl.phase).toBe('popup');
    saved = true;
    await ctl.afterPopup();
    expect(startJob).toHaveBeenCalledTimes(0);
    expect(ctl.phase).toBe('confirming');
    await ctl.confirm();
    expect(startJob).toHaveBeenCalledTimes(1);
  });
});
