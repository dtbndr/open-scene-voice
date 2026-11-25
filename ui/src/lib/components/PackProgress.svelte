<script lang="ts">
  // The running view for aligning or packing: title, "K of N scenes", one row per scene, Cancel for an own run.
  // All strings are in PACK_WORDS (approved). Packing has no rows and no counts: the page passes rows=[] and total=0.
  import { PACK_WORDS, progressLine, rowLine } from '$lib/pack/words';

  let {
    title,
    done,
    total,
    rows,
    canCancel,
    cancelling,
    oncancel
  }: {
    title: string;
    done: number;
    total: number;
    rows: { ordinal: number; status: 'waiting' | 'listening' | 'done' }[];
    canCancel: boolean;
    cancelling: boolean;
    oncancel: () => void;
  } = $props();
</script>

<h1>{title}</h1>
{#if canCancel}
  <button type="button" onclick={oncancel} disabled={cancelling}>{PACK_WORDS.cancel}</button>
  {#if cancelling}<p>{PACK_WORDS.cancelNote}</p>{/if}
{/if}
{#if total > 0}
  <progress max={total} value={done}></progress>
  <p>{progressLine(done, total)}</p>
{/if}
<ul>
  {#each rows as row (row.ordinal)}
    <li>{rowLine(row.ordinal, row.status)}</li>
  {/each}
</ul>
