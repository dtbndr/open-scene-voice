// The pure job reducer (U9). Counts (`total`, `scenes_done`) are never derived here: they come from the job JSON.
import type { CurrentJob, JobEvent, JobState } from '../api/types';

export type SceneStatus = 'started' | 'done' | 'kept';

export interface JobView {
  /** The latest `GET /api/jobs/current` body or the latest `state` / `end` event. */
  readonly current: CurrentJob;
  /** Scene number to status. Set, never incremented. */
  readonly scenes: Readonly<Record<number, SceneStatus>>;
  /** Last applied `seq` per server job number (parsed from the event id `<job>-<seq>`). */
  readonly lastSeq: Readonly<Record<number, number>>;
  /** The message of the latest numbered event. */
  readonly message: string | null;
}

export const emptyView: JobView = Object.freeze({
  current: Object.freeze({ state: 'idle' as JobState, job: null }),
  scenes: Object.freeze({}),
  lastSeq: Object.freeze({}),
  message: null
});

export function isLive(state: JobState): boolean {
  return state === 'starting' || state === 'running' || state === 'cancelling';
}

/** `<job>-<seq>` as the server writes it; anything else is not an event of ours. */
export function parseEventId(id: string): { job: number; seq: number } | null {
  const match = /^(\d+)-(\d+)$/.exec(id);
  return match ? { job: Number(match[1]), seq: Number(match[2]) } : null;
}

/** Take a new job JSON (poll, snapshot or end). After a failed or cancelled job, finished scenes become `kept`. */
export function withCurrent(view: JobView, current: CurrentJob): JobView {
  if (current.state !== 'failed' && current.state !== 'cancelled') return { ...view, current };
  const scenes: Record<number, SceneStatus> = {};
  for (const [number, status] of Object.entries(view.scenes)) {
    if (status === 'done' || status === 'kept') scenes[Number(number)] = 'kept';
  }
  return { ...view, current, scenes };
}

/**
 * Apply one stream event. `job` is the job number from the event id. Job 0 is the connection snapshot (`0-1`) or an
 * idle end: applied on every arrival and outside the cursor. Numbered events are applied once per (job, seq).
 */
export function reduce(view: JobView, event: JobEvent, job: number): JobView {
  if (event.type === 'state' || event.type === 'end') {
    if (job > 0) {
      if (event.seq <= (view.lastSeq[job] ?? 0)) return view;
      view = { ...view, lastSeq: { ...view.lastSeq, [job]: event.seq } };
    }
    return withCurrent(view, { state: event.state, job: event.job });
  }
  if (job <= 0 || event.seq <= (view.lastSeq[job] ?? 0)) return view;
  const next: JobView = { ...view, lastSeq: { ...view.lastSeq, [job]: event.seq }, message: event.message };
  if (event.type !== 'scene' || event.scene === null) return next;
  const known = view.scenes[event.scene];
  if (event.state === 'started' && known !== undefined) return next;
  return { ...next, scenes: { ...view.scenes, [event.scene]: event.state === 'done' ? 'done' : 'started' } };
}
