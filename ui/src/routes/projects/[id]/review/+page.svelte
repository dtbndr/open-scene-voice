<script lang="ts">
  // Screen 7: play each scene back and redo one. The logic lives in `ReviewController`; this page follows its address and renders.
  import { onMount, untrack } from 'svelte';
  import { page } from '$app/state';
  import { jobs } from '$lib/app.svelte';
  import ReviewConfirmDialog from '$lib/components/ReviewConfirmDialog.svelte';
  import ReviewScene from '$lib/components/ReviewScene.svelte';
  import VoiceFailureView from '$lib/components/VoiceFailureView.svelte';
  import VoiceProgress from '$lib/components/VoiceProgress.svelte';
  import { PROGRESS_WORDS, VOICE_WORDS, progressRows } from '$lib/voice/flow';
  import { voiceFailureView } from '$lib/voice/failure';
  import { REVIEW_WORDS } from '$lib/voice/review';
  import { ReviewController } from '$lib/voice/review.svelte';
  const id = $derived(page.params.id ?? '');
  const ctl = new ReviewController(() => id);
  const failure = $derived(ctl.failure ? voiceFailureView(ctl.failure, ctl.failedProvider) : null);
  // The page follows its address: another project's review page starts from scene 1, whatever it was doing.
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
{:else if !ctl.detail}
  <p>Loading...</p>
{:else}
  {#if ctl.notice}
    <p class="problem" role="alert">{ctl.notice}</p>
  {/if}
  {#if ctl.redoing !== null}
    {#if ctl.held.run === null}
      <p>{PROGRESS_WORDS.starting}</p>
    {:else}
      <VoiceProgress
        projectId={id}
        done={ctl.counts?.done ?? 0}
        total={ctl.counts?.total ?? 1}
        rows={progressRows([ctl.redoing], ctl.ownView ? jobs.view.scenes : {})}
        canCancel={true}
        cancelling={ctl.cancelling}
        oncancel={() => ctl.cancel()}
      />
    {/if}
  {:else}
    {#if failure}
      <VoiceFailureView {failure} ontryagain={() => ctl.askRedo()} onback={() => (ctl.failure = null)} />
    {/if}
    <ReviewScene
      projectId={id}
      ordinal={ctl.scene}
      entry={ctl.entry}
      settings={ctl.detail.audio?.settings}
      nonce={ctl.audioNonce}
      hasPrevious={ctl.previous !== null}
      hasNext={ctl.next !== null}
      redo={ctl.redo}
      onprevious={() => ctl.goto(ctl.previous)}
      onnext={() => ctl.goto(ctl.next)}
      onredo={() => ctl.askRedo()}
    />
    {#if ctl.detail.can?.pack}
      <p class="next"><a class="button" href={`/projects/${encodeURIComponent(id)}/pack`}>{REVIEW_WORDS.nextPack}</a></p>
    {/if}
  {/if}
  <ReviewConfirmDialog
    open={ctl.snapshot !== null}
    snapshot={ctl.snapshot}
    settings={ctl.detail.audio?.settings}
    onconfirm={() => ctl.confirm()}
    ondismiss={() => ctl.dismissConfirmation()}
  />
{/if}
<style>
  .problem { color: #a11; }
  .next { margin-top: 1rem; }
  .button { display: inline-block; padding: 0.25rem 0.75rem; border: 1px solid #333; border-radius: 4px; color: inherit; text-decoration: none; }
</style>
