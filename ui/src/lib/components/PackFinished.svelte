<script lang="ts">
  // The done view: where the files are, a folder tree, Show in Finder, an optional zip download, the Resolve hint.
  import { packZipUrl } from '$lib/api/client';
  import { PACK_WORDS } from '$lib/pack/words';

  let { projectId, timeline, canDownload, onreveal }: { projectId: string; timeline: boolean; canDownload: boolean; onreveal: () => void } = $props();

  // packZipUrl throws for an unusable project id: then there is no download to offer.
  const zipHref = $derived.by(() => {
    try {
      return packZipUrl(projectId);
    } catch {
      return null;
    }
  });
</script>

<p>{PACK_WORDS.doneText}</p>
<ul class="tree">
  <li>{projectId}/
    <ul>
      {#if timeline}
        <li>{PACK_WORDS.timelineFile} {PACK_WORDS.timelineNote}</li>
      {/if}
      <li>{PACK_WORDS.manifestFile} {PACK_WORDS.manifestNote}</li>
      <li>{PACK_WORDS.audioDir} {PACK_WORDS.audioNote}</li>
    </ul>
  </li>
</ul>
<button type="button" onclick={onreveal}>{PACK_WORDS.showInFinder}</button>
{#if canDownload && zipHref}
  <a href={zipHref} download data-sveltekit-reload>{PACK_WORDS.downloadZip}</a>
{/if}
<p>{PACK_WORDS.resolveHint}</p>

<style>
  .tree { list-style: none; padding-left: 0; font-family: monospace; }
  .tree ul { list-style: none; padding-left: 1.5rem; }
</style>
