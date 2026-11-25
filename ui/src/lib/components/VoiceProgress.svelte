<script lang="ts">
  // Screen 6 running view: "K of N scenes" from the job JSON, one row per scene (done, voicing, waiting) with a play button
  // for a voiced one, Cancel for an own run. No durations (dropped on purpose). All strings are in PROGRESS_WORDS (proposed).
  import { audioUrl } from '$lib/api/client';
  import { PROGRESS_WORDS, type RowStatus } from '$lib/voice/flow';

  let {
    projectId,
    done,
    total,
    rows,
    canCancel,
    cancelling,
    oncancel
  }: {
    projectId: string;
    done: number;
    total: number;
    rows: { ordinal: number; status: RowStatus }[];
    canCancel: boolean;
    cancelling: boolean;
    oncancel: () => void;
  } = $props();

  let player: HTMLAudioElement | null = null;
  // One scene plays at a time; the browser's own audio does the playing.
  function play(ordinal: number): void {
    try {
      player?.pause();
      player = new Audio(audioUrl(projectId, ordinal));
      void player.play().catch(() => undefined);
    } catch {
      // not a playable project id: nothing to play
    }
  }
  $effect(() => () => player?.pause());
</script>

<h1>{PROGRESS_WORDS.title}</h1>
{#if canCancel}
  <button type="button" onclick={oncancel} disabled={cancelling}>{cancelling ? PROGRESS_WORDS.stopping : PROGRESS_WORDS.cancel}</button>
  <p>{PROGRESS_WORDS.cancelNote}</p>
{/if}
<progress max={Math.max(total, 1)} value={done}></progress>
<p>{done} of {total} scenes</p>
<ul>
  {#each rows as row (row.ordinal)}
    <li>
      {row.ordinal} {PROGRESS_WORDS[row.status]}
      {#if row.status === 'done'}
        <button type="button" onclick={() => play(row.ordinal)}>{PROGRESS_WORDS.play} {row.ordinal}</button>
      {/if}
    </li>
  {/each}
</ul>
<p>{PROGRESS_WORDS.keepOpen}</p>
