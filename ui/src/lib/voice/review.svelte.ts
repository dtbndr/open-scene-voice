// The review page's controller: the current scene, the one-scene redo (its confirmation is the only place a paid job is
// posted from here), the held run and the job-end rule. It reuses the shared pure rules (job-end, guard) and HeldRun; the
// page only renders it. Every late answer is checked against the visit (bumped whenever the page follows a project id).
import { api } from '$lib/api/client';
import { snapshotFor, startBody, type Snapshot } from '$lib/api/confirm';
import { ApiError, FIXED_MESSAGE, NetworkError } from '$lib/api/errors';
import type { Catalog, CurrentJob, ProjectDetail } from '$lib/api/types';
import { jobs } from '$lib/app.svelte';
import { HeldRun } from '$lib/jobs/held-run.svelte';
import { providerName } from './failure';
import type { VoiceFailure } from './flow';
import { providerOf } from './flow';
import { ownership } from './guard';
import { cancelAnswer, resolveEnd, type EndVerdict } from './job-end';
import { REVIEW_WORDS, redoState, stepScene } from './review';

const OWN_KINDS = ['synth-scene'] as const;
const NO_JOB: CurrentJob = { state: 'idle', job: null }; // forces the one lookup of the held run

function words(error: unknown): string {
  return error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE;
}

export class ReviewController {
  readonly held = new HeldRun(); // from this page's own 202 or an own live redo; never replaced from the store
  detail = $state.raw<ProjectDetail | null>(null);
  catalog = $state.raw<Catalog | null>(null);
  problem = $state<string | null>(null);
  notice = $state<string | null>(null);
  failure = $state.raw<VoiceFailure | null>(null);
  snapshot = $state.raw<Snapshot | null>(null);
  scene = $state(1);
  /** The scene of the redo in progress (null when none). */
  redoing = $state<number | null>(null);
  /** The audio element is re-created when this changes, so a finished redo is fetched again. */
  audioNonce = $state(0);
  readonly #id: () => string;
  #visit = 0;
  #alive = true;
  #observing = false;
  #lastSeen: CurrentJob | null = null;
  constructor(id: () => string) {
    this.#id = id;
  }

  readonly ordinals = $derived((this.detail?.script.scenes ?? []).map((entry) => entry.ordinal));
  readonly entry = $derived(this.detail?.audio?.scenes.find((candidate) => candidate.ordinal === this.scene));
  readonly previous = $derived(stepScene(this.ordinals, this.scene, -1));
  readonly next = $derived(stepScene(this.ordinals, this.scene, 1));
  readonly ownView = $derived(this.held.run !== null && jobs.view.current.job?.run === this.held.run);
  readonly cancelling = $derived(this.held.stopping || (this.ownView && jobs.view.current.state === 'cancelling'));
  readonly counts = $derived(this.ownView ? jobs.counts : null);
  /** A live job this page is not running greys Redo and shows the busy note only (no foreign progress, no Cancel). */
  get busy(): boolean {
    return jobs.active && this.redoing === null;
  }
  get redo() {
    return redoState(this.detail?.can, this.busy);
  }
  readonly failedProvider = $derived(providerName(this.catalog ? providerOf(this.catalog, this.detail?.audio?.settings?.model ?? '') : null));

  #stale(visit: number, mine: string): boolean {
    return !this.#alive || visit !== this.#visit || mine !== this.#id();
  }

  /** Start a visit to a project id: another project's page starts from scene 1, whatever it was doing. */
  follow(mine: string): void {
    this.#visit += 1;
    this.detail = null;
    this.catalog = null;
    this.problem = null;
    this.notice = null;
    this.failure = null;
    this.snapshot = null;
    this.scene = 1;
    this.redoing = null;
    this.held.clear();
    this.#observing = false;
    this.#lastSeen = null;
    void this.#load(mine, this.#visit);
  }

  mount(): () => void {
    this.#alive = true;
    const stopListening = jobs.listen(() => this.observe(jobs.view.current));
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
      const [fresh, listed] = await Promise.all([api.project(mine), api.catalog()]);
      if (this.#stale(visit, mine)) return;
      this.catalog = listed;
      this.detail = fresh;
      this.scene = fresh.script.scenes[0]?.ordinal ?? 1;
      await this.#adopt(visit);
    } catch (error) {
      if (!this.#stale(visit, mine)) this.problem = words(error);
    }
  }

  /** Re-entry: an own live redo is shown with Cancel; the run is adopted only when none is held. */
  async #adopt(visit: number): Promise<void> {
    const mine = this.#id();
    try {
      const current = await jobs.refresh();
      if (this.#stale(visit, mine) || !jobs.active || ownership(current.job, mine, OWN_KINDS) !== 'own') return;
      this.held.adopt(current, mine, OWN_KINDS);
      this.redoing = current.job?.scene ?? this.scene;
    } catch {
      // The connection watcher reports an unreachable server.
    }
  }

  async #readDetail(): Promise<void> {
    const mine = this.#id();
    const visit = this.#visit;
    const fresh = await api.project(mine);
    if (!this.#stale(visit, mine)) this.detail = fresh;
  }

  goto(ordinal: number | null): void {
    if (ordinal !== null) this.scene = ordinal;
  }

  /** "Redo this scene": a fresh read, a one-scene snapshot on the recorded settings, then the confirmation. Never posts. */
  async askRedo(): Promise<void> {
    if (this.redo !== 'ready' || this.redoing !== null) return;
    const mine = this.#id();
    const visit = this.#visit;
    this.notice = null;
    this.failure = null;
    try {
      const fresh = await api.project(mine);
      if (this.#stale(visit, mine)) return;
      this.detail = fresh;
      if (fresh.can?.synth_scene !== true) return;
      this.snapshot = snapshotFor('synth-scene', null, fresh, this.scene);
    } catch (error) {
      if (!this.#stale(visit, mine)) this.notice = words(error);
    }
  }

  dismissConfirmation(): void {
    this.snapshot = null;
  }

  // The only place a paid request is posted from this page: the confirmation's own confirm button.
  async confirm(): Promise<void> {
    if (this.snapshot === null || this.redoing !== null) return;
    const body = startBody(this.snapshot);
    const mine = this.#id();
    const visit = this.#visit;
    this.redoing = this.snapshot.scene;
    this.snapshot = null;
    this.held.clear();
    let accepted: CurrentJob;
    try {
      accepted = await api.startJob(mine, body);
    } catch (error) {
      if (this.#stale(visit, mine)) return; // a late answer for another visit changes nothing here
      this.redoing = null;
      this.notice = words(error);
      if (error instanceof ApiError && error.status === 409 && error.kind !== 'busy') await this.#readDetail().catch(() => undefined);
      else if (!(error instanceof ApiError)) await this.#adopt(visit); // the job may have started though the answer was lost
      return;
    }
    if (this.#stale(visit, mine)) return;
    this.held.accept(mine, mine, accepted);
    await this.observe(accepted);
  }

  /** The job-end rule: A is the held run; any observation that is not A-live settles (one lookup of A if it was not seen). */
  async observe(seen: CurrentJob): Promise<void> {
    const run = this.held.run;
    const mine = this.#id();
    const visit = this.#visit;
    if (run === null || this.redoing === null || this.#observing) return;
    this.#observing = true;
    let verdict: EndVerdict;
    try {
      verdict = await resolveEnd(run, seen, api.getJobByRun);
    } finally {
      this.#observing = false;
    }
    if (verdict.settle !== 'ended' || this.#stale(visit, mine) || this.held.run !== run) return; // a lookup error waits for the next poll
    this.held.clear(); // settle first, then refresh: a slow read must not leave the page on "running"
    this.redoing = null;
    this.audioNonce += 1;
    if (verdict.outcome === 'failed') {
      const failure = verdict.failure ?? { kind: 'other' as const, status: null, message: '' };
      this.failure = failure?.kind === 'missing_key' ? { ...failure, kind: 'bad_key' } : failure; // no popup here: "Check my details" opens Keys
    }
    if (verdict.outcome === 'cancelled') this.notice = REVIEW_WORDS.stopped;
    await this.#readDetail().catch(() => undefined);
  }

  async cancel(): Promise<void> {
    const mine = this.#id();
    const visit = this.#visit;
    await this.held.cancel(this.cancelling, api.cancelJob).catch(async (error: unknown) => {
      if (this.#stale(visit, mine)) return;
      const answer = cancelAnswer(error);
      this.notice = answer.notice;
      if (answer.lookup) await this.observe(NO_JOB);
    });
  }
}
