// The run a page holds (its Cancel target). It comes from the page's own accepted start, or is adopted when the guard says
// own (resume, re-entry); the store never replaces it. It is cleared when a new confirm starts, when the run's end is
// handled and when the project changes, so a lost 202 never leaves Cancel pointing at an old run.
import type { CurrentJob, JobKind } from '../api/types';
import { acceptedRun, heldRun } from '../voice/guard';

export class HeldRun {
  run = $state<string | null>(null);
  /** Cancel was pressed and the answer has not come back. */
  stopping = $state(false);

  /** A new confirm starts, or the run ended, or the project changed. */
  clear(): void {
    this.run = null;
    this.stopping = false;
  }

  accept(startedFor: string, project: string, accepted: CurrentJob): void {
    this.run = acceptedRun(startedFor, project, accepted);
    this.stopping = false;
  }

  adopt(current: CurrentJob, project: string, ownKinds: readonly JobKind[]): void {
    this.run = heldRun(this.run, current, project, ownKinds);
  }

  /** Stop the held run. Throws what `stop` throws, after the page can press Cancel again. */
  async cancel(alreadyCancelling: boolean, stop: (run: string) => Promise<unknown>): Promise<void> {
    if (alreadyCancelling || this.run === null) return;
    this.stopping = true;
    try {
      await stop(this.run);
    } catch (error) {
      this.stopping = false;
      throw error;
    }
  }
}
