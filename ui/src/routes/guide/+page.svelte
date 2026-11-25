<script lang="ts">
  import { onMount } from 'svelte';

  type Part = { text: string; code?: boolean };
  type Block = { kind: string; level?: number; text?: string; parts?: Part[]; items?: Part[][] };

  let blocks = $state.raw<Block[] | null>(null);
  let failed = $state(false);

  onMount(async () => {
    try {
      const response = await fetch('/guide.json', { credentials: 'same-origin' });
      if (!response.ok) throw new Error('missing');
      const data: unknown = await response.json();
      const list = (data as { blocks?: unknown }).blocks;
      if (!Array.isArray(list)) throw new Error('shape');
      blocks = list as Block[];
    } catch {
      failed = true;
    }
  });

  function tag(level: number | undefined): string {
    const n = typeof level === 'number' ? Math.min(Math.max(Math.trunc(level), 1), 6) : 2;
    return `h${n}`;
  }
</script>

<svelte:head>
  <title>Script guide - SceneVoice</title>
</svelte:head>

<article>
  <p class="back">Back to the script: close this tab. Your script is still open in the first tab.</p>
  {#if failed}
    <p role="alert">The script guide could not be loaded. Close this tab and try again.</p>
  {:else if blocks === null}
    <p>Loading...</p>
  {:else}
    {#each blocks as block, index (index)}
      {#if block.kind === 'heading'}
        <svelte:element this={tag(block.level)}>{block.text ?? ''}</svelte:element>
      {:else if block.kind === 'paragraph'}
        <p>{@render runs(block.parts ?? [])}</p>
      {:else if block.kind === 'list'}
        <ul>
          {#each block.items ?? [] as item, itemIndex (itemIndex)}
            <li>{@render runs(item)}</li>
          {/each}
        </ul>
      {:else if block.kind === 'code'}
        <pre><code>{block.text ?? ''}</code></pre>
      {:else}
        <p>{block.text ?? ''}</p>
      {/if}
    {/each}
  {/if}
</article>

{#snippet runs(parts: Part[])}{#each parts as part, partIndex (partIndex)}{#if part.code}<code>{part.text}</code>{:else}{part.text}{/if}{/each}{/snippet}

<style>
  article {
    max-width: 44rem;
    margin: 0 auto;
    padding: 1rem;
    line-height: 1.5;
  }
  .back {
    color: #555;
  }
  pre {
    background: #f4f4f4;
    padding: 0.75rem;
    overflow-x: auto;
    white-space: pre-wrap;
  }
  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
</style>
