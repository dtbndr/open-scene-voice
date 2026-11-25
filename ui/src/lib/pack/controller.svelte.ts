// The Pack page's controller: update (free or paid), the key popup, the confirmation (the only place a paid job is posted),
// pack, the held run and its end, cancel and reveal. Job mechanics live in ./job; the page only renders this.
// Every late answer is checked against the visit (bumped whenever the page follows a project id).
import { api } from '$lib/api/client';
import { snapshotFor, startBody, type Snapshot } from '$lib/api/confirm';
import type { CurrentJob, KeyName, ProjectDetail, StartBody } from '$lib/api/types';
import { jobs } from '$lib/app.svelte';
import { HeldRun } from '$lib/jobs/held-run.svelte';
import { missingKeys } from '$lib/keys.svelte';
import { ownership } from '$lib/voice/guard';
import type { AlignFailureShown, PackFailureView } from './failure';
import { NO_JOB, cancelRun, sceneRows, settleRun, startRun, words, type SceneRowStatus, type Settled } from './job';
import { needsOpenRouterKey, updatePlan } from './rules';
import { PACK_WORDS } from './words';

const OWN_KINDS = ['align', 'pack'] as const;
const OPENROUTER: KeyName[] = ['OPENROUTER_API_KEY'];

export type PackPhase = 'idle' | 'confirming' | 'popup' | 'running' | 'failed' | 'stopped';
/** What the controller uses of the client and the job store (a fake stands in for them in tests). */
export interface PackDeps {
  api: Pick<typeof api, 'project' | 'keys' | 'startJob' | 'cancelJob' | 'getJobByRun' | 'reveal'>;
  jobs: Pick<typeof jobs, 'active' | 'view' | 'counts' | 'refresh' | 'listen'>;
}

export class PackController {
  readonly held = new HeldRun(); // from this page's own 202 or an own live run; never replaced from the store
  detail = $state.raw<ProjectDetail | null>(null);
  problem = $state<string | null>(null);
  notice = $state<string | null>(null);
  phase = $state<PackPhase>('idle');
  /** Frozen when the confirmation opened, from a fresh read; the only thing a paid post is built from. */
  snapshot = $state.raw<Snapshot | null>(null);
  popupMissing = $state.raw<KeyName[]>([]);
  failure = $state.raw<AlignFailureShown | PackFailureView | null>(null);
  /** The kind of the run in progress or just ended (for retry). */
  kind = $state<'align' | 'pack' | null>(null);
  #pending = $state.raw<number[]>([]);
  readonly #id: () => string;
  readonly #api: PackDeps['api'];
  readonly #jobs: PackDeps['jobs'];
  #visit = 0;
  #alive = true;
  #observing = false;
  #lastSeen: CurrentJob | null = null;
  constructor(id: () => string, deps: PackDeps = { api, jobs }) {
    this.#id = id;
    this.#api = deps.api;
    this.#jobs = deps.jobs;
  }

  get ownView(): boolean { return this.held.run !== null && this.#jobs.view.current.job?.run === this.held.run; }
  get cancelling(): boolean { return this.held.stopping || (this.ownView && this.#jobs.view.current.state === 'cancelling'); }
  get counts(): { done: number; total: number } | null {
    return this.ownView ? this.#jobs.counts : null;
  }
  /** Per-scene rows for a running align (waiting | listening | done). */
  get rows(): { ordinal: number; status: SceneRowStatus }[] {
    return this.ownView && this.kind === 'align' ? sceneRows(this.#pending, this.#jobs.view.scenes) : [];
  }
  get packing(): boolean { return this.phase === 'running' && this.kind === 'pack'; }
  /** Cancel is offered for the held align run only (pack is short and free). */
  get canCancel(): boolean { return this.phase === 'running' && this.kind === 'align' && this.held.run !== null; }
  /** A live job this page is not running: the busy note only, no progress, no Cancel. */
  get foreignBusy(): boolean { return this.#jobs.active && this.phase !== 'running'; }

  #stale(visit: number, mine: string): boolean {
    return !this.#alive || visit !== this.#visit || mine !== this.#id();
  }

  follow(mine: string): void {
    this.#visit += 1;
    this.detail = null;
    this.problem = null;
    this.#clearRun();
    this.#pending = [];
    void this.#load(mine, this.#visit);
  }

  #clearRun(): void {
    this.notice = null;
    this.failure = null;
    this.snapshot = null;
    this.popupMissing = [];
    this.phase = 'idle';
    this.kind = null;
    this.held.clear();
    this.#observing = false;
    this.#lastSeen = null;
  }

  mount(): () => void {
    this.#alive = true;
    const stopListening = this.#jobs.listen(() => this.observe(this.#jobs.view.current));
    return () => {
      this.#alive = false;
      stopListening();
    };
  }

  /** Every new job JSON (poll or stream) is an observation of the held run. */
  see(seen: CurrentJob): void {
    if (seen === this.#lastSeen) return;
    this.#lastSeen = seen;
    void this.observe(seen);
  }

  async #load(mine: string, visit: number): Promise<void> {
    try {
      const fresh = await this.#api.project(mine);
      if (this.#stale(visit, mine)) return;
      this.detail = fresh;
      await this.#adopt(visit, mine, true);
    } catch (error) {
      if (!this.#stale(visit, mine)) this.problem = words(error);
    }
  }

  async #readDetail(visit: number, mine: string): Promise<void> {
    try {
      const fresh = await this.#api.project(mine);
      if (!this.#stale(visit, mine)) this.detail = fresh;
    } catch {
      // The connection watcher reports an unreachable server; the old detail stays.
    }
  }

  /** "Update line markers": a fresh read; free posts the echo with no dialog; paid checks the key, then opens the
   * confirmation. Paid never posts from here (see confirm). */
  async update(): Promise<void> {
    if (this.phase === 'running') return;
    const mine = this.#id();
    const visit = this.#visit;
    this.notice = null;
    this.failure = null;
    this.snapshot = null;
    this.popupMissing = [];
    this.phase = 'idle';
    try {
      const fresh = await this.#api.project(mine);
      if (this.#stale(visit, mine)) return;
      this.detail = fresh;
      const plan = updatePlan(fresh);
      if (plan === 'unavailable') return;
      this.#pending = fresh.line_markers?.stale_scenes ?? [];
      if (plan === 'free') return await this.#start(startBody(snapshotFor('align', null, fresh)), mine, visit);
      if (needsOpenRouterKey(fresh)) {
        const missing = missingKeys(OPENROUTER, await this.#api.keys());
        if (this.#stale(visit, mine)) return;
        if (missing.length > 0) {
          this.popupMissing = missing;
          this.phase = 'popup';
          return;
        }
      }
      this.snapshot = snapshotFor('align', null, fresh);
      this.phase = 'confirming';
    } catch (error) {
      if (!this.#stale(visit, mine)) this.notice = words(error);
    }
  }

  /** The key popup saved: a fresh read and a fresh confirmation. Never posts. */
  async afterPopup(): Promise<void> {
    this.popupMissing = [];
    this.phase = 'idle';
    await this.update();
  }

  /** Back from a failure or a stop: clear them and show the idle page again (the detail stays). */
  back(): void {
    this.failure = null;
    this.notice = null;
    this.snapshot = null;
    this.phase = 'idle';
  }

  dismiss(): void {
    this.snapshot = null;
    this.popupMissing = [];
    this.phase = 'idle';
  }

  // The only place a paid request is posted: the confirmation's own confirm button, from its frozen snapshot.
  async confirm(): Promise<void> {
    if (this.snapshot === null || this.phase !== 'confirming') return;
    const body = startBody(this.snapshot);
    this.snapshot = null;
    await this.#start(body, this.#id(), this.#visit);
  }

  /** Pack: no echo, no dialog. */
  async packNow(): Promise<void> {
    if (this.phase === 'running') return;
    this.notice = null;
    this.failure = null;
    await this.#start({ kind: 'pack' }, this.#id(), this.#visit);
  }

  /** Try again on a failure or a stop: the same step again from a fresh read (never a blind re-post). */
  async retry(): Promise<void> {
    if (this.kind === 'pack') await this.packNow();
    else await this.update();
  }

  async #start(body: StartBody, mine: string, visit: number): Promise<void> {
    this.held.clear();
    this.kind = body.kind === 'pack' ? 'pack' : 'align';
    this.phase = 'running';
    const result = await startRun(this.#api.startJob, mine, body);
    if (this.#stale(visit, mine)) return; // a late answer for another visit changes nothing here
    if (!result.ok) {
      this.phase = 'idle';
      this.notice = result.text;
      if (result.reread) await this.#readDetail(visit, mine);
      else if (result.lost) await this.#adopt(visit, mine);
      return;
    }
    this.held.accept(mine, mine, result.accepted);
    await this.observe(result.accepted);
  }

  /** Re-entry, or a lost start answer (the job may be running): an own live run is held, only when none is. */
  async #adopt(visit: number, mine: string, throws = false): Promise<void> {
    try {
      const current = await this.#jobs.refresh();
      if (this.#stale(visit, mine) || !this.#jobs.active || ownership(current.job, mine, OWN_KINDS) !== 'own') return;
      this.held.adopt(current, mine, OWN_KINDS);
      this.kind = current.job?.kind === 'pack' ? 'pack' : 'align';
      this.phase = 'running';
    } catch (error) {
      if (throws) throw error; // the page load shows it; a lost-answer adopt leaves it to the connection watcher
    }
  }

  /** The job-end rule: any observation that is not the held run's live JSON settles it (one lookup if it was not seen). */
  async observe(seen: CurrentJob): Promise<void> {
    const run = this.held.run;
    const kind = this.kind;
    const mine = this.#id();
    const visit = this.#visit;
    if (run === null || kind === null || this.#observing) return;
    this.#observing = true;
    let settled: Settled;
    try {
      settled = await settleRun(run, seen, this.#api.getJobByRun, kind);
    } finally {
      this.#observing = false;
    }
    if (!settled.ended || this.#stale(visit, mine) || this.held.run !== run) return; // a lookup error waits for the next poll
    this.held.clear(); // settle first, then refresh: a slow read must not leave the page on "running"
    if (settled.outcome === 'done') this.phase = 'idle';
    else if (settled.outcome === 'stopped') {
      this.phase = 'stopped';
      this.notice = PACK_WORDS.stopped;
    } else if (settled.outcome === 'popup') {
      this.popupMissing = OPENROUTER; // a missing_key failure: retry only from a fresh read, after the save
      this.phase = 'popup';
    } else if (settled.outcome === 'failed') {
      this.failure = settled.view;
      this.phase = 'failed';
    }
    await this.#readDetail(visit, mine);
  }

  /** Cancel the held align run (pack has no Cancel). A refused Cancel looks the run up once. */
  async cancel(): Promise<void> {
    if (!this.canCancel) return;
    const mine = this.#id();
    const visit = this.#visit;
    const answer = await cancelRun(this.held, this.cancelling, this.#api.cancelJob);
    if (answer === null || this.#stale(visit, mine)) return;
    this.notice = answer.notice;
    if (answer.lookup) await this.observe(NO_JOB);
  }

  async reveal(): Promise<void> {
    const mine = this.#id();
    const visit = this.#visit;
    try {
      await this.#api.reveal(mine);
    } catch (error) {
      if (!this.#stale(visit, mine)) this.notice = words(error);
    }
  }
}
