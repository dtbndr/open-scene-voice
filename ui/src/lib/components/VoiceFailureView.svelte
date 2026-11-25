<script lang="ts">
  // The voicing failure view: wording and buttons come from `voiceFailureView` (pure). "Check my details" opens Keys.
  import { FAILURE_WORDS, type VoiceFailureView } from '$lib/voice/failure';
  let { failure, ontryagain, onback }: { failure: VoiceFailureView; ontryagain: () => void; onback: () => void } = $props();
</script>
{#if failure.heading}<p><strong>{failure.heading}</strong></p>{/if}
<p class="problem" role="alert">{failure.text}</p>
{#each failure.buttons as button (button)}
  {#if button === 'tryAgain'}
    <button type="button" onclick={ontryagain}>{FAILURE_WORDS.tryAgain}</button>
  {:else if button === 'checkDetails'}
    <a href="/keys">{FAILURE_WORDS.checkDetails}</a>
  {:else}
    <button type="button" onclick={onback}>{FAILURE_WORDS.back}</button>
  {/if}
{/each}
<style>
  .problem { color: #a11; }
</style>
