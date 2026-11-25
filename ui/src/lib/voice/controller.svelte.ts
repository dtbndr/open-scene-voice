// The voice page's controller: the choice flow, the confirmation (the only place a paid job is posted), the held run and
// the job-end rule. The page only renders it. Every late answer is checked against the visit visit (bumped each time the
// page follows a project id) as well as the id, so X to Y to X never applies an answer from the first visit to the second.
import { api } from '$lib/api/client';
import { snapshotFor, startBody, type Snapshot } from '$lib/api/confirm';
import { ApiError, FIXED_MESSAGE, NetworkError } from '$lib/api/errors';
import type { Catalog, CurrentJob, KeyName, ProjectDetail } from '$lib/api/types';
import { jobs } from '$lib/app.svelte';
import { HeldRun } from '$lib/jobs/held-run.svelte';
import { missingKeys } from '$lib/keys.svelte';
import { offeredModes, runModelFor, sceneSets } from './cancelled';
import { providerName } from './failure';
import { ownership } from './guard';
import { cancelAnswer, resolveEnd, type EndVerdict } from './job-end';
import { VoiceModel } from './voice.svelte';
import { VOICE_WORDS, chooseKind, costFor, defaultMode, entryOf, neededKeys, pendingOrdinals, providerOf, radioModels, settleMode, type VoiceMode } from './flow';

const OWN_KINDS = ['synth', 'synth-scene'] as const;
const NO_JOB: CurrentJob = { state: 'idle', job: null }; // forces the one lookup of the held run

function words(error: unknown): string {
  return error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE;
}

export class VoiceController {
  readonly voice = new VoiceModel();
  readonly held = new HeldRun(); // from this page's own 202 or an own live run; never replaced from the store
  detail = $state.raw<ProjectDetail | null>(null);
  catalog = $state.raw<Catalog | null>(null);
  problem = $state<string | null>(null);
  snapshot = $state.raw<Snapshot | null>(null);
  pending = $state.raw<number[]>([]); // the scene numbers of the running job
  popupMissing = $state.raw<KeyName[]>([]);
  /** The model of the run in progress or just ended: its keys feed the missing-key popup, not the current radio. */
  runModel = $state('');
  readonly #id: () => string;
  #visit = 0;
  #alive = true;
  #observing = false;
  #lastSeen: CurrentJob | null = null;
  constructor(id: () => string) {
    this.#id = id;
  }

  readonly phase = $derived(this.voice.phase.phase);
  readonly entry = $derived(this.detail ? entryOf(this.detail) : 'fresh');
  readonly fullView = $derived(this.entry === 'full' && !this.voice.again && this.voice.phase.phase === 'choose');
  readonly modes = $derived<VoiceMode[]>(
    this.detail === null
      ? []
      : this.entry === 'fresh'
        ? ['all']
        : offeredModes(this.detail.can)
  );
  /** The scenes voiced and not voiced as of the last detail read (the cancelled page names them). */
  readonly sets = $derived(this.detail ? sceneSets(this.detail) : { voiced: [], unvoiced: [] });
  readonly kind = $derived(this.detail ? chooseKind(this.detail.can, this.voice.mode) : null);
  readonly locked = $derived(this.voice.mode === 'rest' && this.detail ? (this.detail.audio?.settings ?? null) : null);
  /** The model whose provider is used: the recorded one for the rest, the chosen radio otherwise. */
  readonly usedModel = $derived(this.locked?.model ?? this.voice.modelId);
  readonly cost = $derived(this.detail && this.kind ? costFor(this.detail, this.voice.mode, this.usedModel) : null);
  readonly voiceReady = $derived(this.locked !== null || (this.catalog !== null && this.voice.voiceFor(this.catalog) !== ''));
  readonly ownView = $derived(this.held.run !== null && jobs.view.current.job?.run === this.held.run);
  /** Cancel is in flight: this page's press, or the job JSON of the held run says so (never another run's). */
  readonly cancelling = $derived(this.held.stopping || (this.ownView && jobs.view.current.state === 'cancelling'));
  readonly counts = $derived(this.ownView ? jobs.counts : null);
  readonly canPress = $derived(this.kind !== null && this.cost !== null && this.voiceReady && !jobs.active && this.phase === 'choose');
  /** The foreign-job view: a live job that is not this project's voicing shows the busy note only. */
  get foreignBusy(): boolean {
    return jobs.active && this.phase === 'choose' && ownership(jobs.view.current.job, this.#id(), OWN_KINDS) === 'foreign';
  }
  /** Which provider a failure view names: the run's model, else the current choice. */
  readonly failedProvider = $derived(providerName(this.catalog ? providerOf(this.catalog, this.runModel || this.usedModel) : null));

  #stale(visit: number, mine: string): boolean {
    return !this.#alive || visit !== this.#visit || mine !== this.#id();
  }

  /** Start a visit to a project id: another project's page starts from the choice view, whatever phase it was in. */
  follow(mine: string): void {
    this.#visit += 1;
    this.detail = null;
    this.catalog = null;
    this.problem = null;
    this.snapshot = null;
    this.pending = [];
    this.runModel = '';
    this.held.clear();
    this.#observing = false;
    this.#lastSeen = null;
    this.voice.reset();
    void this.#load(mine, this.#visit);
  }

  /** Every new job JSON (poll or stream) is an observation of the held run. */
  see(seen: CurrentJob): void {
    if (seen === this.#lastSeen) return;
    this.#lastSeen = seen;
    void this.observe(seen);
  }

  /** Listen to the store's end events; returns the teardown. */
  mount(): () => void {
    this.#alive = true;
    const stopListening = jobs.listen(() => this.observe(jobs.view.current));
    return () => {
      this.#alive = false;
      stopListening();
    };
  }

  async #load(mine: string, visit: number): Promise<void> {
    try {
      const [fresh, listed] = await Promise.all([api.project(mine), api.catalog()]);
      if (this.#stale(visit, mine)) return;
      this.catalog = listed;
      this.detail = fresh;
      this.voice.init(listed, defaultMode(entryOf(fresh), fresh.can), radioModels(listed)[0]?.id ?? '');
      await this.#resumeIfRunning(visit);
    } catch (error) {
      if (!this.#stale(visit, mine)) this.problem = words(error);
    }
  }

  /** Re-read the detail and freeze a snapshot of it. Never posts. Returns false with a notice when it cannot. */
  async #prepare(retry = false): Promise<boolean> {
    const mine = this.#id();
    const visit = this.#visit;
    try {
      const fresh = await api.project(mine);
      if (this.#stale(visit, mine) || this.catalog === null) return false;
      this.detail = fresh;
      this.voice.mode = settleMode(fresh, this.voice.mode, retry);
      const chosen = chooseKind(fresh.can, this.voice.mode);
      if (chosen === null) {
        this.voice.notice = VOICE_WORDS.unavailable;
        return false;
      }
      const withText = providerOf(this.catalog, this.voice.modelId)?.voices !== null;
      this.snapshot = snapshotFor(chosen.kind, chosen.mode, fresh, undefined, this.voice.modelId, {
        voice: this.voice.voiceFor(this.catalog),
        language: withText ? this.voice.language.trim() : undefined,
        instruction: withText ? this.voice.style.trim() : undefined
      });
      return true;
    } catch (error) {
      if (!this.#stale(visit, mine)) this.voice.notice = words(error);
      return false;
    }
  }

  async press(): Promise<void> {
    if (!this.canPress || this.catalog === null) return;
    const mine = this.#id();
    const visit = this.#visit;
    this.voice.notice = null;
    const needed = neededKeys(providerOf(this.catalog, this.usedModel));
    let missing: KeyName[];
    try {
      missing = missingKeys(needed, await api.keys());
    } catch (error) {
      if (!this.#stale(visit, mine)) this.voice.notice = words(error);
      return;
    }
    if (this.#stale(visit, mine)) return;
    if (missing.length > 0) {
      this.popupMissing = missing;
      this.voice.send({ type: 'press', keysMissing: true });
    } else if (await this.#prepare()) {
      this.voice.send({ type: 'press', keysMissing: false });
    }
  }

  // The popup callback re-reads the detail and opens a fresh confirmation; it never posts a job.
  async afterPopup(): Promise<void> {
    this.voice.send({ type: (await this.#prepare()) ? 'popupDone' : 'popupCancel' });
  }

  /** "Try again": always a fresh read and a fresh confirmation (the rest after a partial run), never a direct post. */
  async tryAgain(): Promise<void> {
    this.voice.notice = null;
    if (await this.#prepare(true)) this.voice.send({ type: 'tryAgain' });
  }

  // The only place a paid request is posted: the confirmation's own confirm button.
  async confirm(): Promise<void> {
    if (this.voice.phase.phase !== 'confirming' || this.snapshot === null) return;
    const body = startBody(this.snapshot);
    const mine = this.#id();
    const visit = this.#visit;
    this.runModel = this.snapshot.model ?? this.usedModel;
    this.pending = this.detail ? pendingOrdinals(this.detail, this.snapshot.mode) : [];
    this.snapshot = null;
    this.held.clear();
    this.voice.send({ type: 'confirm' });
    let accepted: CurrentJob;
    try {
      accepted = await api.startJob(mine, body);
    } catch (error) {
      if (this.#stale(visit, mine)) return; // a late answer for another visit changes nothing here
      this.voice.notice = words(error);
      const kind = error instanceof ApiError ? error.kind : '';
      this.voice.send({ type: 'rejected', reason: kind === 'busy' || kind === 'changed' ? kind : 'not_allowed' });
      if (error instanceof ApiError) {
        if (error.status === 409 && kind !== 'busy') await this.#readDetail().catch(() => undefined);
      } else {
        await this.#resumeIfRunning(visit);
      }
      return;
    }
    if (this.#stale(visit, mine)) return;
    this.held.accept(mine, mine, accepted);
    this.voice.send({ type: 'started' });
    await this.observe(accepted);
  }

  async #readDetail(): Promise<void> {
    const mine = this.#id();
    const visit = this.#visit;
    const fresh = await api.project(mine);
    if (!this.#stale(visit, mine)) this.detail = fresh;
  }

  /** After an answer we could not read, a job may still have started: show it rather than pretend it did not. */
  async #resumeIfRunning(visit: number): Promise<void> {
    const mine = this.#id();
    try {
      const current = await jobs.refresh();
      if (!this.#stale(visit, mine) && jobs.active && ownership(current.job, mine, OWN_KINDS) === 'own' && this.voice.phase.phase === 'choose') {
        this.held.adopt(current, mine, OWN_KINDS);
        this.pending = this.detail ? pendingOrdinals(this.detail, current.job?.mode ?? null) : [];
        this.runModel = runModelFor(this.detail?.audio?.settings, this.usedModel);
        this.voice.notice = null;
        this.voice.send({ type: 'resumed' });
      }
    } catch {
      // The connection watcher reports an unreachable server.
    }
  }

  /** The job-end rule: A is the held run; any observation that is not A-live settles (one lookup of A if it was not seen). */
  async observe(seen: CurrentJob): Promise<void> {
    const run = this.held.run;
    const mine = this.#id();
    const visit = this.#visit;
    if (run === null || this.voice.phase.phase !== 'running' || this.#observing) return;
    this.#observing = true;
    let verdict: EndVerdict;
    try {
      verdict = await resolveEnd(run, seen, api.getJobByRun);
    } finally {
      this.#observing = false;
    }
    if (verdict.settle !== 'ended' || this.#stale(visit, mine) || this.held.run !== run) return; // a lookup error waits for the next poll
    this.held.clear();
    const needed = verdict.failure?.kind === 'missing_key' && this.catalog !== null ? neededKeys(providerOf(this.catalog, this.runModel || this.usedModel)) : []; // the failed job's model
    if (needed.length > 0) this.popupMissing = needed;
    this.voice.send({ type: 'ended', outcome: verdict.outcome, failure: verdict.failure }); // settle first: a slow read must not leave "Generating" up
    await this.#readDetail().catch(() => undefined); // the ended view then names the scenes as they are now
    if (needed.length === 0) return;
    try {
      const missing = missingKeys(needed, await api.keys());
      if (missing.length > 0 && !this.#stale(visit, mine)) this.popupMissing = missing;
    } catch {
      // the popup keeps listing every key the provider needs
    }
  }

  async cancel(): Promise<void> {
    const mine = this.#id();
    const visit = this.#visit;
    await this.held.cancel(this.cancelling, api.cancelJob).catch(async (error: unknown) => {
      if (this.#stale(visit, mine)) return;
      const answer = cancelAnswer(error);
      this.voice.notice = answer.notice;
      if (answer.lookup) await this.observe(NO_JOB);
    });
  }

  /** "Voice the rest" (recorded settings, a fresh confirmation) or "Start again" (the full choice): never posts a job. */
  async offer(mode: VoiceMode): Promise<void> {
    if (!offeredModes(this.detail?.can).includes(mode)) return;
    this.voice.send({ type: 'back' });
    this.voice.mode = mode;
    this.voice.again = mode === 'restart';
    this.voice.notice = null;
    if (mode === 'rest') await this.press();
  }

  dismissConfirmation(): void {
    this.snapshot = null;
    this.voice.send({ type: 'dismiss' });
  }
}
