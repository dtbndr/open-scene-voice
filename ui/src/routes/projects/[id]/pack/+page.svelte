<script lang="ts">
  // Screen 8: line markers and packing for Resolve. The logic lives in `PackController`; this page follows its address and renders.
  import { onMount, untrack } from 'svelte';
  import { page } from '$app/state';
  import { jobs } from '$lib/app.svelte';
  import MissingKeyPopup from '$lib/components/MissingKeyPopup.svelte';
  import PackAlignDialog from '$lib/components/PackAlignDialog.svelte';
  import PackFailureView from '$lib/components/PackFailureView.svelte';
  import PackFinished from '$lib/components/PackFinished.svelte';
  import PackMarkers from '$lib/components/PackMarkers.svelte';
  import PackProgress from '$lib/components/PackProgress.svelte';
  import { PackController } from '$lib/pack/controller.svelte';
  import { canDownload } from '$lib/pack/rules';
  import { PACK_WORDS, markersLine } from '$lib/pack/words';
  import { VOICE_WORDS } from '$lib/voice/flow';
  const id = $derived(page.params.id ?? '');
  const ctl = new PackController(() => id);
  // The page follows its address: another project's pack page starts from idle, whatever it was doing.
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

{#snippet markersAndFinished()}
  {#if ctl.detail}
    <PackMarkers
      markersText={markersLine(ctl.detail.line_markers)}
      busy={ctl.phase === 'confirming' || ctl.phase === 'popup'}
      canAlign={ctl.detail.can?.align === true}
      canPack={ctl.detail.can?.pack === true}
      onupdate={() => ctl.update()}
      onpack={() => ctl.packNow()}
    />
    {#if ctl.detail.pack?.manifest}
      <PackFinished
        projectId={id}
        timeline={ctl.detail.pack.timeline === true}
        canDownload={canDownload(ctl.detail, jobs.active)}
        onreveal={() => ctl.reveal()}
      />
    {/if}
  {/if}
{/snippet}

<p><a href={`/projects/${encodeURIComponent(id)}`}>{VOICE_WORDS.back}</a></p>
{#if ctl.problem}
  <p class="problem" role="alert">{ctl.problem}</p>
{:else if !ctl.detail}
  <p>Loading...</p>
{:else}
  {#if ctl.phase === 'running'}
    <PackProgress
      title={ctl.packing ? PACK_WORDS.packing : PACK_WORDS.updating}
      done={ctl.counts?.done ?? 0}
      total={ctl.counts?.total ?? 0}
      rows={ctl.rows}
      canCancel={ctl.canCancel}
      cancelling={ctl.cancelling}
      oncancel={() => ctl.cancel()}
    />
  {:else if ctl.phase === 'failed' && ctl.failure}
    <PackFailureView failure={ctl.failure} ontryagain={() => ctl.retry()} onback={() => ctl.back()} />
  {:else if ctl.phase === 'stopped'}
    {@render markersAndFinished()}
    <p role="status">{ctl.notice}</p>
    <button type="button" onclick={() => ctl.retry()}>{PACK_WORDS.tryAgain}</button>
    <button type="button" onclick={() => ctl.back()}>{PACK_WORDS.back}</button>
  {:else if ctl.foreignBusy}
    <p role="status">{PACK_WORDS.busy}</p>
  {:else if ctl.detail.can?.pack !== true}
    <p>{PACK_WORDS.needsVoice}</p>
    <p><a href={`/projects/${encodeURIComponent(id)}/voice`}>{PACK_WORDS.backToVoice}</a></p>
  {:else}
    {#if ctl.notice}
      <p class="problem" role="alert">{ctl.notice}</p>
    {/if}
    {@render markersAndFinished()}
  {/if}
  {#if ctl.phase === 'popup'}
    <MissingKeyPopup missing={ctl.popupMissing} onsaved={() => ctl.afterPopup()} oncancel={() => ctl.dismiss()} />
  {/if}
  <PackAlignDialog open={ctl.phase === 'confirming'} snapshot={ctl.snapshot} onconfirm={() => ctl.confirm()} ondismiss={() => ctl.dismiss()} />
{/if}

<style>
  .problem { color: #a11; }
</style>
