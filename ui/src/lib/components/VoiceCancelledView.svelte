<script lang="ts">
  // The cancelled run: which scenes were kept and which were not, the quota note, and the two offers the server's `can`
  // allows. Pressing an offer never posts a job; the page opens a fresh choice or confirmation.
  import { CANCELLED_WORDS, cancelledText } from '$lib/voice/cancelled';
  import type { VoiceMode } from '$lib/voice/flow';

  let {
    voiced,
    unvoiced,
    offers,
    onoffer,
    onback
  }: {
    voiced: number[];
    unvoiced: number[];
    offers: VoiceMode[];
    onoffer: (mode: VoiceMode) => void;
    onback: () => void;
  } = $props();
</script>

<p role="status">{cancelledText(voiced, unvoiced)}</p>
<p>{CANCELLED_WORDS.quotaNote}</p>
{#each offers as mode (mode)}
  <button type="button" onclick={() => onoffer(mode)}>{mode === 'rest' ? CANCELLED_WORDS.rest : CANCELLED_WORDS.restart}</button>
{/each}
<button type="button" onclick={onback}>{CANCELLED_WORDS.back}</button>
