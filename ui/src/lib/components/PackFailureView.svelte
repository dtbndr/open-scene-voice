<script lang="ts">
  // The align or pack failure view: wording and buttons come from the pure views in `$lib/pack/failure`.
  // "Check my details" opens Keys. Only the align view carries a footer.
  import type { AlignFailureShown, PackFailureView as PackFailureShape } from '$lib/pack/failure';
  import { PACK_WORDS } from '$lib/pack/words';

  let { failure, ontryagain, onback }: { failure: AlignFailureShown | PackFailureShape; ontryagain: () => void; onback: () => void } = $props();
</script>

<p><strong>{failure.heading}</strong></p>
<p class="problem" role="alert">{failure.text}</p>
{#if 'footer' in failure}<p>{failure.footer}</p>{/if}
{#each failure.buttons as button (button)}
  {#if button === 'tryAgain'}
    <button type="button" onclick={ontryagain}>{PACK_WORDS.tryAgain}</button>
  {:else if button === 'checkDetails'}
    <a href="/keys">{PACK_WORDS.checkDetails}</a>
  {:else}
    <button type="button" onclick={onback}>{PACK_WORDS.back}</button>
  {/if}
{/each}

<style>
  .problem { color: #a11; }
</style>
