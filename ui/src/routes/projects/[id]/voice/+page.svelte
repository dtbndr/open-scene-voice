<script lang="ts">
  // Screens 5 and 6: the choice view, the confirmation, progress, Cancel, the job-end rule and the failure and foreign-job
  // views. The logic lives in `VoiceController`; this page follows its address and renders.
  import { onMount, untrack } from 'svelte';
  import { page } from '$app/state';
  import { jobs } from '$lib/app.svelte';
  import MissingKeyPopup from '$lib/components/MissingKeyPopup.svelte';
  import VoiceCancelledView from '$lib/components/VoiceCancelledView.svelte';
  import VoiceChoice from '$lib/components/VoiceChoice.svelte';
  import VoiceConfirmDialog from '$lib/components/VoiceConfirmDialog.svelte';
  import VoiceFailureView from '$lib/components/VoiceFailureView.svelte';
  import VoiceProgress from '$lib/components/VoiceProgress.svelte';
  import { offeredModes } from '$lib/voice/cancelled';
  import { VoiceController } from '$lib/voice/controller.svelte';
  import { voiceFailureView } from '$lib/voice/failure';
  import { PROGRESS_WORDS, VOICE_WORDS, progressRows } from '$lib/voice/flow';
  const id = $derived(page.params.id ?? '');
  const ctl = new VoiceController(() => id);
  const voice = ctl.voice;
  const failure = $derived(voice.phase.phase === 'failed' ? voiceFailureView(voice.phase.failure, ctl.failedProvider) : null);
  // The page follows its address: another project's voice page starts from the choice view, whatever phase it was in.
  $effect(() => {
    const mine = id;
    untrack(() => ctl.follow(mine));
  });
  // Every new job JSON (poll or stream) is an observation of the held run.
  $effect(() => {
    const seen = jobs.view.current;
    untrack(() => ctl.see(seen));
  });
  onMount(() => ctl.mount());
</script>
<p><a href={`/projects/${encodeURIComponent(id)}`}>{VOICE_WORDS.back}</a></p>
{#if ctl.problem}
  <p class="problem" role="alert">{ctl.problem}</p>
{:else if !ctl.detail || !ctl.catalog}
  <p>Loading...</p>
{:else}
  {#if voice.notice}
    <p class="problem" role="alert">{voice.notice}</p>
  {/if}
  {#if ctl.foreignBusy}
    <p role="status">{VOICE_WORDS.busyForeign}</p>
  {:else if ctl.fullView}
    <h1>{VOICE_WORDS.title}</h1>
    <p>{VOICE_WORDS.fullyVoiced}</p>
    <p><a href={`/projects/${encodeURIComponent(id)}/review`}>{VOICE_WORDS.toReview}</a></p>
    {#if ctl.detail.can?.synth?.restart}
      <button
        type="button"
        onclick={() => {
          voice.again = true;
          voice.mode = 'restart';
        }}>{VOICE_WORDS.startAgain}</button
      >
    {/if}
  {:else if ctl.phase === 'starting'}
    <p>{PROGRESS_WORDS.starting}</p>
  {:else if ctl.phase === 'running'}
    <VoiceProgress
      projectId={id}
      done={ctl.counts?.done ?? 0}
      total={ctl.counts?.total ?? ctl.pending.length}
      rows={progressRows(ctl.pending, ctl.ownView ? jobs.view.scenes : {})}
      canCancel={ctl.held.run !== null}
      cancelling={ctl.cancelling}
      oncancel={() => ctl.cancel()}
    />
  {:else if ctl.phase === 'showing'}
    <!-- Stand-in until the review slice: the finished job leads to the review screen. -->
    <p>{VOICE_WORDS.fullyVoiced}</p>
    <p><a href={`/projects/${encodeURIComponent(id)}/review`}>{VOICE_WORDS.toReview}</a></p>
  {:else if ctl.phase === 'cancelled'}
    <VoiceCancelledView
      voiced={ctl.sets.voiced}
      unvoiced={ctl.sets.unvoiced}
      offers={offeredModes(ctl.detail.can)}
      onoffer={(mode) => ctl.offer(mode)}
      onback={() => voice.send({ type: 'back' })}
    />
  {:else if failure}
    <VoiceFailureView {failure} ontryagain={() => ctl.tryAgain()} onback={() => voice.send({ type: 'back' })} />
  {:else if ctl.phase === 'choose' || ctl.phase === 'popup' || ctl.phase === 'confirming'}
    <VoiceChoice
      catalog={ctl.catalog}
      model={voice}
      locked={ctl.locked}
      modes={ctl.modes}
      cost={ctl.cost}
      canPress={ctl.canPress}
      busy={jobs.active}
      unavailable={ctl.kind === null}
      onpress={() => ctl.press()}
    />
  {/if}
  {#if ctl.phase === 'popup'}
    <MissingKeyPopup missing={ctl.popupMissing} onsaved={() => ctl.afterPopup()} oncancel={() => voice.send({ type: 'popupCancel' })} />
  {/if}
  <VoiceConfirmDialog open={ctl.phase === 'confirming'} snapshot={ctl.snapshot} onconfirm={() => ctl.confirm()} ondismiss={() => ctl.dismissConfirmation()} />
{/if}
<style>
  .problem { color: #a11; }
</style>
