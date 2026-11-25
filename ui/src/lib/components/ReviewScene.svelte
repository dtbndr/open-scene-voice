<script lang="ts">
  // One scene of the review screen: the browser's own audio player, Prev and Next, and Redo. No scene text and no scene
  // strip (dropped on purpose). The audio element is re-created when `nonce` changes, so a finished redo is fetched again.
  import { audioUrl } from '$lib/api/client';
  import type { AudioScene, AudioSettings } from '$lib/api/types';
  import { REVIEW_WORDS, sceneNotes, settingsLine, type RedoState } from '$lib/voice/review';

  let {
    projectId,
    ordinal,
    entry,
    settings,
    nonce,
    hasPrevious,
    hasNext,
    redo,
    onprevious,
    onnext,
    onredo
  }: {
    projectId: string;
    ordinal: number;
    entry: AudioScene | undefined;
    settings: AudioSettings | null | undefined;
    nonce: number;
    hasPrevious: boolean;
    hasNext: boolean;
    redo: RedoState;
    onprevious: () => void;
    onnext: () => void;
    onredo: () => void;
  } = $props();
</script>

<h1>{REVIEW_WORDS.title}</h1>
{#if settings}
  <p>{settingsLine(settings)}</p>
{/if}
<h2>Scene {ordinal}</h2>
{#if entry?.voiced}
  {#key `${ordinal}-${nonce}`}
    <audio controls preload="none" src={audioUrl(projectId, ordinal)}></audio>
  {/key}
{:else}
  <p>{REVIEW_WORDS.notVoiced}</p>
{/if}
{#each sceneNotes(entry) as note (note)}
  <p role="status">{note}</p>
{/each}
<div class="buttons">
  <button type="button" onclick={onprevious} disabled={!hasPrevious}>{REVIEW_WORDS.previous}</button>
  {#if redo !== 'hidden'}
    <button type="button" onclick={onredo} disabled={redo === 'busy'}>{REVIEW_WORDS.redo}</button>
  {/if}
  <button type="button" onclick={onnext} disabled={!hasNext}>{REVIEW_WORDS.next}</button>
</div>
{#if redo === 'busy'}
  <p role="status">{REVIEW_WORDS.busy}</p>
{/if}

<style>
  .buttons { display: flex; gap: 0.5rem; margin: 1rem 0; }
  audio { width: 100%; max-width: 30rem; }
</style>
