// The voice page's job-end rule and its Cancel answers (pure). The page holds a run id A; this decides from what it saw
// whether A is still live or has ended, so the page never stays on "running" after the job is over.
import { ApiError, FIXED_MESSAGE, NetworkError } from '../api/errors';
import { isLive } from '../jobs/reduce';
import type { CurrentJob } from '../api/types';
import type { VoiceFailure } from './flow';

// Approved wording (owner, WS47).
export const ENDED_WORDS = 'This voicing has ended. Check which scenes were voiced, then carry on.';
export const CANCEL_MISMATCH_WORDS = 'That voicing was no longer running, so nothing was stopped.';

export type EndVerdict =
  | { settle: 'live' }
  | { settle: 'wait' }
  | { settle: 'ended'; outcome: 'done' | 'cancelled' | 'failed'; failure?: VoiceFailure };

const endedVerdict = (message: string): EndVerdict => ({ settle: 'ended', outcome: 'failed', failure: { kind: 'other', status: null, message } });

/** What A's own job JSON says: live, or its final with its own failure. Null when the JSON is not A's. */
function ownVerdict(run: string, seen: CurrentJob): EndVerdict | null {
  if (seen.job?.run !== run) return null;
  if (isLive(seen.state)) return { settle: 'live' };
  if (seen.state === 'done') return { settle: 'ended', outcome: 'done' };
  if (seen.state === 'cancelled') return { settle: 'ended', outcome: 'cancelled' };
  return { settle: 'ended', outcome: 'failed', ...(seen.job.failure ? { failure: seen.job.failure } : {}) };
}

/**
 * Any observation that is not A-live settles. A's own JSON decides directly; no job or another run makes ONE lookup of A
 * (live stays, a retained final settles with its failure, 404 settles with the generic wording). A lookup that fails any
 * other way waits for the next poll.
 */
export async function resolveEnd(
  run: string,
  seen: CurrentJob,
  lookup: (run: string) => Promise<CurrentJob>,
  ended: string = ENDED_WORDS
): Promise<EndVerdict> {
  const direct = ownVerdict(run, seen);
  if (direct) return direct;
  try {
    return ownVerdict(run, await lookup(run)) ?? endedVerdict(ended);
  } catch (error) {
    return error instanceof ApiError && error.status === 404 ? endedVerdict(ended) : { settle: 'wait' };
  }
}

/** A Cancel that failed: 409 changed and 404 not_found both mean the run is not live, so look it up (409 also says so in words). */
export function cancelAnswer(error: unknown): { lookup: boolean; notice: string | null } {
  if (error instanceof ApiError && error.status === 409 && error.kind === 'changed') return { lookup: true, notice: CANCEL_MISMATCH_WORDS };
  if (error instanceof ApiError && error.status === 404) return { lookup: true, notice: null };
  return { lookup: false, notice: error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE };
}
