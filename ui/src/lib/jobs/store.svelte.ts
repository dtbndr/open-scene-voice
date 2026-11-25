// The one job store (U9): the job JSON, the scene map and the one event stream. It is the only place that
// opens the stream. WS46 and WS47 read `view`, `counts`, `active`, `settled` and set `onEnd`.
import { EVENTS_URL } from '../api/client';
import type { CurrentJob, JobEvent } from '../api/types';
import { emptyView, isLive, parseEventId, reduce, withCurrent, type JobView } from './reduce';

/** The part of `EventSource` the store uses; a fake stands in for it in tests. */
export interface EventSourceLike {
  readyState: number;
  onmessage: ((event: { data: string; lastEventId: string }) => void) | null;
  onerror: ((event: unknown) => void) | null;
  close(): void;
}

export interface JobStoreOptions {
  fetchJob: () => Promise<CurrentJob>;
  createSource: (url: string) => EventSourceLike;
  /** Called once per finished job after the job JSON was re-read: the page re-reads that project's detail. */
  onEnd?: (project: string | null) => void | Promise<void>;
}

const OPEN = 1; // EventSource.OPEN, spelled out so the store also runs where EventSource does not exist.

export class JobStore {
  /** The reduced view: `current` (job JSON), `scenes` (number to started | done | kept), `message`. */
  view = $state.raw<JobView>(emptyView);
  /** False from a job's end until the re-read (and `onEnd`) has finished. */
  settled = $state(true);
  /** Local counter: a new live job (or a different run, even of the same kind and project) is a new generation. */
  generation = $state(0);
  /** Set by the page that owns the open project (WS46); may be replaced at any time. */
  onEnd: ((project: string | null) => void | Promise<void>) | undefined;

  #listeners = new Set<(project: string | null) => void | Promise<void>>();
  #fetchJob: () => Promise<CurrentJob>;
  #createSource: (url: string) => EventSourceLike;
  #source: EventSourceLike | null = null;
  #wasLive = false;
  #key: string | null = null;
  #reconciled = -1;

  constructor(options: JobStoreOptions) {
    this.#fetchJob = options.fetchJob;
    this.#createSource = options.createSource;
    this.onEnd = options.onEnd;
  }

  /** Add an end listener next to `onEnd` (a page registers on mount and calls the returned function on destroy). */
  listen(handler: (project: string | null) => void | Promise<void>): () => void {
    this.#listeners.add(handler);
    return () => {
      this.#listeners.delete(handler);
    };
  }

  /** True while the stream is OPEN (a stream that is reconnecting does not count). */
  get streamOpen(): boolean {
    return this.#source !== null && this.#source.readyState === OPEN;
  }

  get active(): boolean {
    return isLive(this.view.current.state);
  }

  /** Counts for display, from the job JSON only. A finished job with no scenes done (pack) shows none. */
  get counts(): { done: number; total: number } | null {
    const job = this.view.current.job;
    if (job === null || job.total <= 0) return null;
    if (job.finished && job.scenes_done === 0) return null;
    return { done: job.scenes_done, total: job.total };
  }

  /** One `GET /api/jobs/current`; the connection watcher calls this as its poll. Throws what the client throws. */
  async refresh(): Promise<CurrentJob> {
    const current = await this.#fetchJob();
    this.#take(current, false);
    this.view = withCurrent(this.view, current);
    return current;
  }

  /** Decide the generation and the stream for a job JSON seen from a poll or from the stream. */
  #take(current: CurrentJob, fromStream: boolean): void {
    const live = isLive(current.state);
    const key = current.job?.run ?? null;
    const wasLive = this.#wasLive;
    if (live && (!wasLive || key !== this.#key)) {
      this.generation += 1;
      this.view = emptyView;
      if (!fromStream) this.#closeStream();
    }
    if (live && !fromStream && this.#source === null) this.#openStream();
    if (key !== null) this.#key = key;
    this.#wasLive = live;
    if (wasLive && !live) void this.#reconcile(this.generation);
  }

  #openStream(): void {
    const source = this.#createSource(EVENTS_URL);
    this.#source = source;
    source.onmessage = (message) => {
      if (this.#source === source) this.#receive(message.data, message.lastEventId);
    };
  }

  #closeStream(): void {
    this.#source?.close();
    this.#source = null;
  }

  #receive(data: string, id: string): void {
    const at = parseEventId(id);
    let event: JobEvent;
    try {
      event = JSON.parse(data) as JobEvent;
    } catch {
      return;
    }
    if (at === null || typeof event !== 'object' || event === null) return;
    if (event.type === 'state' || event.type === 'end') this.#take({ state: event.state, job: event.job }, true);
    this.view = reduce(this.view, event, at.job);
    if (event.type === 'end') void this.#reconcile(this.generation);
  }

  /** Once per generation: re-read the job, let the page re-read the project, settle, and only then close the stream. */
  async #reconcile(generation: number): Promise<void> {
    if (this.#reconciled === generation) return;
    this.#reconciled = generation;
    this.settled = false;
    const source = this.#source;
    const project = this.view.current.job?.project ?? null;
    try {
      const current = await this.#fetchJob();
      this.#take(current, false);
      this.view = withCurrent(this.view, current);
    } catch {
      // The connection watcher reports an unreachable server; the stream is closed below either way.
    }
    for (const handler of [this.onEnd, ...this.#listeners]) {
      try {
        await handler?.(project);
      } catch {
        // The page shows its own error for its own re-read.
      }
    }
    this.settled = true;
    if (source !== null && this.#source === source) this.#closeStream();
  }
}
