<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { page } from '$app/state';
  import { api } from '$lib/api/client';
  import { snapshotFor, startBody, type Snapshot } from '$lib/api/confirm';
  import { ApiError, FIXED_MESSAGE, NetworkError } from '$lib/api/errors';
  import type { CurrentJob, KeyName, ProjectDetail } from '$lib/api/types';
  import { jobs } from '$lib/app.svelte';
  import { HeldRun } from '$lib/jobs/held-run.svelte';
  import { ownership } from '$lib/voice/guard';
  import { BeatsModel } from '$lib/beats/beats.svelte';
  import { CANCELLED_WORDS, INVALID_BEATS_WORDS, chooseKind, failureWording, type BeatsFailure } from '$lib/beats/flow';
  import BeatsConfirmDialog from '$lib/components/BeatsConfirmDialog.svelte';
  import BeatsFailureView from '$lib/components/BeatsFailureView.svelte';
  import BeatsModelField from '$lib/components/BeatsModelField.svelte';
  import BeatsProgress from '$lib/components/BeatsProgress.svelte';
  import { usableScenes, type BeatsScene } from '$lib/beats/guard';
  import BeatsList from '$lib/components/BeatsList.svelte';
  import NextVoice from '$lib/components/NextVoice.svelte';
  import MissingKeyPopup from '$lib/components/MissingKeyPopup.svelte';
  import { missingKeys } from '$lib/keys.svelte';

  const CHARACTER_LIMIT = 20000;
  const KEY: KeyName = 'OPENROUTER_API_KEY';
  const OWN_KINDS = ['beats', 'beats-redo'] as const;

  const id = $derived(page.params.id ?? '');
  const beats = new BeatsModel();
  let detail = $state.raw<ProjectDetail | null>(null);
  let problem = $state<string | null>(null);
  let snapshot = $state.raw<Snapshot | null>(null);
  let popupMissing = $state.raw<KeyName[]>([]);
  let scenes = $state.raw<BeatsScene[] | null>(null);
  const held = new HeldRun(); // from this page's own accepted start or an own live run; never replaced from the store
  let alive = true;
  let ending = false;

  const phase = $derived(beats.phase.phase);
  const failure = $derived(beats.phase.phase === 'failed' ? failureWording(beats.phase.failure) : null);
  const withinLimit = $derived((detail?.script?.total_characters ?? Infinity) <= CHARACTER_LIMIT);
  const savedState = $derived(detail?.beats?.state);
  const hasSaved = $derived(savedState === 'fresh' || savedState === 'stale');
  const unreadable = $derived(savedState === 'invalid' || (scenes !== null && scenes.length === 0));
  const redoing = $derived(hasSaved || savedState === 'invalid' || phase === 'showing');
  const kind = $derived(detail ? chooseKind(detail.can) : null);
  const canPress = $derived(beats.hasModel && withinLimit && kind !== null && !jobs.active);
  const fieldShown = $derived(phase === 'choose' || phase === 'cancelled' || phase === 'showing');
  const cancelling = $derived(held.stopping || jobs.view.current.state === 'cancelling');

  function words(error: unknown): string {
    return error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE;
  }

  async function readDetail(): Promise<ProjectDetail> {
    const mine = id;
    const fresh = await api.project(mine);
    if (alive && mine === id) detail = fresh;
    return fresh;
  }

  /** Re-read the detail and freeze a snapshot of it. Never posts. Returns false with a notice when it cannot. */
  async function prepare(): Promise<boolean> {
    try {
      const fresh = await readDetail();
      const chosen = chooseKind(fresh.can);
      if (chosen === null) {
        beats.notice = 'Visual beats cannot be planned for this project right now.';
        return false;
      }
      snapshot = snapshotFor(chosen, null, fresh, undefined, beats.modelName.trim());
      return true;
    } catch (error) {
      beats.notice = words(error);
      return false;
    }
  }

  async function press() {
    if (!canPress) return;
    beats.notice = null;
    if (phase === 'cancelled') beats.send({ type: 'back' });
    if (phase === 'showing') beats.send({ type: 'redo' });
    let missing: KeyName[];
    try {
      missing = missingKeys([KEY], await api.keys());
    } catch (error) {
      beats.notice = words(error);
      return;
    }
    if (missing.length > 0) {
      popupMissing = missing;
      beats.send({ type: 'press', keysMissing: true });
    } else if (await prepare()) {
      beats.send({ type: 'press', keysMissing: false });
    }
  }

  // The popup callback re-reads the detail and opens the confirmation; it never posts a job.
  async function afterPopup() {
    beats.send({ type: (await prepare()) ? 'popupDone' : 'popupCancel' });
  }

  // The only place a paid request is posted: the confirmation's own confirm button.
  async function confirm() {
    if (beats.phase.phase !== 'confirming' || snapshot === null) return;
    const body = startBody(snapshot);
    const mine = id;
    snapshot = null;
    held.clear();
    beats.send({ type: 'confirm' });
    let accepted: CurrentJob;
    try {
      accepted = await api.startJob(mine, body);
    } catch (error) {
      if (mine !== id) return; // a late answer for another project's visit changes nothing here
      beats.notice = words(error);
      const reason = error instanceof ApiError ? (error.kind === 'busy' ? 'busy' : error.status === 409 ? 'changed' : 'not_allowed') : 'not_allowed';
      beats.send({ type: 'rejected', reason });
      if (error instanceof ApiError) {
        if (error.status === 409 && error.kind !== 'busy') await readDetail().catch(() => undefined);
      } else {
        await resumeIfRunning();
      }
      return;
    }
    if (mine !== id) return;
    held.accept(mine, id, accepted);
    beats.send({ type: 'started' });
    await settleAfterStart();
  }

  /** A job that ended before this read is never seen as running, so no end event comes: finish it here. */
  async function settleAfterStart() {
    try {
      await jobs.refresh();
    } catch {
      return; // The connection watcher reports an unreachable server and the next poll settles the page.
    }
    if (!jobs.active && ownership(jobs.view.current.job, id, OWN_KINDS) === 'own') await onJobEnd(id);
  }

  /** After an answer we could not read, a job may still have started: show it rather than pretend it did not. */
  async function resumeIfRunning() {
    const mine = id;
    try {
      const current = await jobs.refresh();
      if (mine === id && jobs.active && ownership(current.job, id, OWN_KINDS) === 'own') {
        held.adopt(current, id, OWN_KINDS);
        beats.notice = null;
        beats.send({ type: 'resumed' });
      }
    } catch {
      // The connection watcher reports an unreachable server.
    }
  }

  function dismissConfirmation() {
    snapshot = null;
    beats.send({ type: 'dismiss' });
  }

  async function cancelJob() {
    await held.cancel(cancelling, api.cancelJob).catch((error: unknown) => {
      beats.notice = words(error);
    });
  }

  // The list is built from the route's document, never from a stream event; an older list stays until the new one is read.
  async function showResult(mine: string) {
    let next: BeatsScene[];
    try {
      next = usableScenes(await api.beats(mine));
    } catch {
      next = [];
    }
    if (alive && mine === id) scenes = next;
  }

  async function onJobEnd(project: string | null) {
    if (!alive || ending || project !== id || beats.phase.phase !== 'running') return;
    ending = true;
    try {
      await finishJob();
    } finally {
      ending = false;
    }
  }

  async function finishJob() {
    const current = jobs.view.current;
    await readDetail().catch(() => undefined);
    if (!alive) return;
    held.clear();
    if (current.state === 'done') {
      beats.send({ type: 'ended', outcome: 'done' });
      await showResult(id);
    } else if (current.state === 'cancelled') {
      beats.send({ type: 'ended', outcome: 'cancelled' });
    } else {
      const raw = current.job?.failure;
      const failed: BeatsFailure | undefined = raw ? { kind: raw.kind, status: raw.status, message: raw.message } : undefined;
      if (failed?.kind === 'missing_key') {
        try {
          const missing = missingKeys([KEY], await api.keys());
          popupMissing = missing.length > 0 ? missing : [KEY];
        } catch {
          popupMissing = [KEY];
        }
      }
      beats.send({ type: 'ended', outcome: 'failed', failure: failed });
    }
  }

  async function tryAgain() {
    if (await prepare()) beats.send({ type: 'tryAgain' });
  }

  async function load(mine: string) {
    try {
      const fresh = await api.project(mine);
      if (!alive || mine !== id) return;
      detail = fresh;
      if (fresh.beats?.state === 'fresh' || fresh.beats?.state === 'stale') void showResult(mine);
      await resumeIfRunning();
    } catch (error) {
      if (alive && mine === id) problem = words(error);
    }
  }

  // The page follows its address: another project's beats page starts from nothing.
  $effect(() => {
    const mine = id;
    untrack(() => {
      detail = null;
      scenes = null;
      problem = null;
      snapshot = null;
      held.clear();
      beats.notice = null;
      if (beats.phase.phase !== 'running') beats.phase = { phase: 'choose' };
      void load(mine);
    });
  });

  onMount(() => {
    alive = true;
    const stopListening = jobs.listen(onJobEnd);
    return () => {
      alive = false;
      stopListening();
    };
  });
</script>

<p><a href={`/projects/${encodeURIComponent(id)}`}>Back</a></p>
<h1>Scene and visual beats</h1>

{#if problem}
  <p class="problem" role="alert">{problem}</p>
{:else if !detail}
  <p>Loading...</p>
{:else}
  {#if beats.notice}
    <p class="problem" role="alert">{beats.notice}</p>
  {/if}

  {#if phase === 'running'}
    <BeatsProgress {cancelling} canCancel={held.run !== null} oncancel={cancelJob} />
  {:else if phase === 'starting'}
    <p>Starting...</p>
  {:else if failure}
    <BeatsFailureView {failure} ontryagain={tryAgain} onback={() => beats.send({ type: 'back' })} />
  {:else if phase === 'cancelled'}
    <p>{CANCELLED_WORDS}</p>
  {/if}

  {#if scenes?.length}<BeatsList {scenes} />{/if}
  {#if unreadable}
    <p class="problem" role="alert">{INVALID_BEATS_WORDS}</p>
  {/if}
  {#if savedState === 'stale' && phase !== 'running' && phase !== 'starting'}
    <p role="status">The script has changed since these beats were made.</p>
  {/if}

  {#if fieldShown}
    <BeatsModelField bind:model={beats.modelName} {withinLimit} {canPress} {redoing} onpress={press} />
  {/if}

  {#if phase === 'popup'}
    <MissingKeyPopup missing={popupMissing} onsaved={afterPopup} oncancel={() => beats.send({ type: 'popupCancel' })} />
  {/if}

  <BeatsConfirmDialog open={phase === 'confirming'} onconfirm={confirm} ondismiss={dismissConfirmation} />
  <NextVoice {id} enabled={phase !== 'running' && phase !== 'starting' && !jobs.active && Object.values(detail.can?.synth ?? {}).some(Boolean)} />
{/if}

<style>
  .problem { color: #a11; }
</style>
