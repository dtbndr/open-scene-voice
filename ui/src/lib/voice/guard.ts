// The foreign-job guard (pure). It decides whether a page may adopt the live run as its own (resume, re-entry) and when
// to show the busy note; it never decides what Cancel stops (the run id does) or when a page settles.
import type { CurrentJob, JobInfo, JobKind } from '../api/types';

export type Ownership = 'own' | 'foreign' | 'none';

/** Own = this project and one of the page's own kinds; any other running job is foreign. */
export function ownership(job: JobInfo | null | undefined, project: string, ownKinds: readonly JobKind[]): Ownership {
  if (!job) return 'none';
  return job.project === project && ownKinds.includes(job.kind) ? 'own' : 'foreign';
}

/** The run a page holds: the one it holds; else the store's live run only when it is own; else none. */
export function heldRun(held: string | null, current: CurrentJob, project: string, ownKinds: readonly JobKind[]): string | null {
  if (held !== null) return held;
  return ownership(current.job, project, ownKinds) === 'own' ? (current.job?.run ?? null) : null;
}

/** A start answer sets the held run only while the page still shows the project that started it. */
export function acceptedRun(startedFor: string, project: string, accepted: CurrentJob): string | null {
  return startedFor === project ? (accepted.job?.run ?? null) : null;
}
