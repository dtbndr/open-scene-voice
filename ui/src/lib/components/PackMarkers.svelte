<script lang="ts">
  // The markers section of the Pack screen: what goes into the timeline, the line-marker status, and the two actions.
  // All wording is in PACK_WORDS (approved); the page decides `busy`, `canAlign` and `canPack`.
  import { PACK_WORDS } from '$lib/pack/words';

  let {
    markersText,
    busy,
    canAlign,
    canPack,
    onupdate,
    onpack
  }: { markersText: string; busy: boolean; canAlign: boolean; canPack: boolean; onupdate: () => void; onpack: () => void } = $props();
</script>

<h1>{PACK_WORDS.title}</h1>
<p>{PACK_WORDS.markersIntro}</p>
<ul>
  <li>{PACK_WORDS.sceneMarkers} &ndash; {PACK_WORDS.alwaysIncluded}</li>
  <li>{PACK_WORDS.markersLabel} &ndash; {markersText}</li>
</ul>
<p>{PACK_WORDS.lineHint}</p>
<button type="button" onclick={onupdate} disabled={busy || !canAlign}>{PACK_WORDS.updateButton}</button>
<button type="button" onclick={onpack} disabled={busy || !canPack}>{PACK_WORDS.packButton}</button>
