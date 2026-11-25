<script lang="ts">
  import type { CheckView } from '$lib/script/script.svelte';

  let {
    check,
    checkError,
    checking,
    empty,
    onShowLine
  }: {
    check: CheckView;
    checkError: string | null;
    checking: boolean;
    empty: boolean;
    onShowLine: (line: number) => void;
  } = $props();
</script>

{#if !empty}
  <section class="problems" aria-label="Problems">
    {#if checkError}
      <p class="problem" role="alert">{checkError}</p>
    {:else if check && !check.ok}
      <p class="problem">
        <strong>Line {check.problem.line}:</strong>
        {check.problem.message}
      </p>
      <p class="actions">
        <button type="button" onclick={() => onShowLine(check.problem.line)}>Show line {check.problem.line}</button>
        <a href="/guide" target="_blank" rel="noopener">Script guide</a>
      </p>
      <p class="count">1 problem to fix.</p>
    {:else if check}
      <p class="count">No problems found. {check.scenes} {check.scenes === 1 ? 'scene' : 'scenes'}.</p>
    {:else if checking}
      <p class="count">Checking...</p>
    {/if}
  </section>
{/if}

<style>
  .problems { border-top: 1px solid #d8d8d8; margin-top: 0.5rem; padding-top: 0.5rem; }
  .problem { color: #a11; margin: 0.25rem 0; }
  .actions { display: flex; gap: 1rem; align-items: baseline; margin: 0.25rem 0; }
  .count { color: #555; margin: 0.25rem 0; }
</style>
