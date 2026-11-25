// Pack job mechanics (no state): start a job and map its refusals, settle a held run's end, cancel it, and map the
// per-scene stream to the rows the page shows. The controller holds the page state and calls these.
import { ApiError, FIXED_MESSAGE, NetworkError } from '../api/errors';
import type { CurrentJob, StartBody } from '../api/types';
import type { HeldRun } from '../jobs/held-run.svelte';
import type { SceneStatus } from '../jobs/reduce';
import { cancelAnswer, resolveEnd } from '../voice/job-end';
import { alignFailureView, packFailureView, type AlignFailureShown, type PackFailureView } from './failure';
import { PACK_WORDS } from './words';

/** Forces the one lookup of the held run. */
export const NO_JOB: CurrentJob = { state: 'idle', job: null };

export function words(error: unknown): string {
  return error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE;
}

/** `reread`: a 409 other than busy (the numbers moved or the step is not allowed); `lost`: no answer at all, so the job may
 * have started anyway. A refused request is never retried by the caller. */
export type StartResult = { ok: true; accepted: CurrentJob } | { ok: false; text: string; reread: boolean; lost: boolean };

export async function startRun(start: (id: string, body: StartBody) => Promise<CurrentJob>, id: string, body: StartBody): Promise<StartResult> {
  try {
    return { ok: true, accepted: await start(id, body) };
  } catch (error) {
    const known = error instanceof ApiError;
    return { ok: false, text: words(error), reread: known && error.status === 409 && error.kind !== 'busy', lost: !known };
  }
}

export type Settled =
  | { ended: false }
  | { ended: true; outcome: 'done' | 'stopped' | 'popup' }
  | { ended: true; outcome: 'failed'; view: AlignFailureShown | PackFailureView };

/** The job-end rule for the held run `run` of kind `kind`, with the pack wording. */
export async function settleRun(run: string, seen: CurrentJob, lookup: (run: string) => Promise<CurrentJob>, kind: 'align' | 'pack'): Promise<Settled> {
  const verdict = await resolveEnd(run, seen, lookup, PACK_WORDS.ended);
  if (verdict.settle !== 'ended') return { ended: false };
  if (verdict.outcome === 'done') return { ended: true, outcome: 'done' };
  if (verdict.outcome === 'cancelled') return { ended: true, outcome: 'stopped' };
  const failure = verdict.failure ?? { kind: 'other' as const, status: null, message: '' };
  if (kind === 'pack') return { ended: true, outcome: 'failed', view: packFailureView(failure) };
  const view = alignFailureView(failure);
  return view.popup ? { ended: true, outcome: 'popup' } : { ended: true, outcome: 'failed', view };
}

/** Stop the held run. Null when the stop was accepted (or nothing was held); else the Cancel answer to show. */
export async function cancelRun(held: HeldRun, cancelling: boolean, stop: (run: string) => Promise<unknown>): Promise<{ lookup: boolean; notice: string | null } | null> {
  try {
    await held.cancel(cancelling, stop);
    return null;
  } catch (error) {
    return cancelAnswer(error);
  }
}

export type SceneRowStatus = 'waiting' | 'listening' | 'done';
/** One row per scene listened to (the ones the page knew at the start and any the stream reported), in order. */
export function sceneRows(pending: readonly number[], seen: Readonly<Record<number, SceneStatus>>): { ordinal: number; status: SceneRowStatus }[] {
  const ordinals = [...new Set([...pending, ...Object.keys(seen).map(Number)])].sort((a, b) => a - b);
  return ordinals.map((ordinal) => {
    const status = seen[ordinal];
    return { ordinal, status: status === 'done' || status === 'kept' ? 'done' : status === 'started' ? 'listening' : 'waiting' };
  });
}
