<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import { connection } from '$lib/app.svelte';
  import EarlierRunPage from '$lib/components/EarlierRunPage.svelte';
  import StoppedPage from '$lib/components/StoppedPage.svelte';
  import { launchCheck } from '$lib/first-launch.svelte';

  let { children } = $props();

  onMount(() => {
    // The first-launch check belongs to a page load that opens on `/`.
    if (page.url.pathname !== '/') launchCheck.done = true;
    connection.start();
    return () => connection.stop();
  });
</script>

{#if connection.state === 'stopped'}
  <StoppedPage />
{:else if connection.state === 'earlier'}
  <EarlierRunPage />
{:else}
  <header>
    <span class="brand">SceneVoice</span>
    <nav>
      <a href="/" aria-current={page.url.pathname === '/' ? 'page' : undefined}>Projects</a>
      <a href="/keys" aria-current={page.url.pathname === '/keys' ? 'page' : undefined}>Keys</a>
    </nav>
  </header>
  <main>
    {@render children()}
  </main>
{/if}

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  }
  header {
    display: flex;
    align-items: baseline;
    gap: 1.5rem;
    padding: 0.75rem 1.5rem;
    border-bottom: 1px solid #d8d8d8;
  }
  .brand { font-weight: 600; }
  nav { display: flex; gap: 1rem; }
  a[aria-current='page'] { font-weight: 600; }
  main { padding: 0 1.5rem 2rem; }
</style>
