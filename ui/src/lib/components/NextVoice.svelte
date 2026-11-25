<script lang="ts">
  /** The way on to the voice screen; a disabled button until the page says the step is ready. */
  let { id, enabled }: { id: string; enabled: boolean } = $props();
</script>

<p class="next">
  {#if enabled}
    <a class="button" href={`/projects/${encodeURIComponent(id)}/voice`}>Next: Voice</a>
  {:else}
    <button type="button" disabled>Next: Voice</button>
  {/if}
</p>

<style>
  .next { margin-top: 1rem; }
  .button { display: inline-block; padding: 0.25rem 0.75rem; border: 1px solid #333; border-radius: 4px; color: inherit; text-decoration: none; }
</style>
