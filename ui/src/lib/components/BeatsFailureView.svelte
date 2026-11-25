<script lang="ts">
  import type { FailureWording } from '$lib/beats/flow';

  let { failure, ontryagain, onback }: { failure: FailureWording; ontryagain: () => void; onback: () => void } = $props();
</script>

{#if failure.heading}<p><strong>{failure.heading}</strong></p>{/if}
<p class="problem" role="alert">{failure.text}</p>
{#each failure.buttons as button (button)}
  {#if button === 'tryAgain'}
    <button type="button" onclick={ontryagain}>Try again</button>
  {:else if button === 'checkKey'}
    <a href="/keys">Check my key</a>
  {:else}
    <button type="button" onclick={onback}>Back</button>
  {/if}
{/each}

<style>
  .problem { color: #a11; }
</style>
