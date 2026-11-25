<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, isProjectId } from '$lib/api/client';
  import { ApiError, NetworkError } from '$lib/api/errors';
  import type { ProjectEntry } from '$lib/api/types';
  import { firstLaunch, launchCheck } from '$lib/first-launch.svelte';

  let workspace = $state('');
  let projects = $state<ProjectEntry[]>([]);
  let loaded = $state(false);
  let loadError = $state<string | null>(null);
  let name = $state('');
  let createError = $state<string | null>(null);
  let creating = $state(false);

  function messageOf(error: unknown): string {
    return error instanceof ApiError || error instanceof NetworkError
      ? error.message
      : 'SceneVoice could not finish. Try again.';
  }

  function dateOf(seconds: number): string {
    return new Date(seconds * 1000).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  onMount(async () => {
    try {
      const [keys, list] = await Promise.all([api.keys(), api.projects()]);
      workspace = list.workspace;
      projects = list.projects;
      loaded = true;
      if (!launchCheck.done) {
        launchCheck.done = true;
        const anyKey = Object.values(keys.keys).some((status) => status.saved);
        if (!anyKey && list.projects.length === 0) {
          firstLaunch.value = true;
          await goto('/keys');
        }
      }
    } catch (error) {
      launchCheck.done = true;
      loadError = messageOf(error);
    }
  });

  async function create(event: SubmitEvent) {
    event.preventDefault();
    if (creating) return;
    creating = true;
    createError = null;
    try {
      const created = await api.createProject(name);
      if (!isProjectId(created.id)) {
        createError = 'SceneVoice could not finish. Try again.';
        return;
      }
      await goto(`/projects/${created.id}`);
    } catch (error) {
      createError = messageOf(error);
    } finally {
      creating = false;
    }
  }
</script>

<h1>Projects</h1>

{#if loadError}
  <p class="problem" role="alert">{loadError}</p>
{:else if !loaded}
  <p>Loading...</p>
{:else}
  <p class="workspace">Your projects live in {workspace}</p>

  {#if projects.length === 0}
    <p class="empty">Make your first project</p>
  {:else}
    <ul class="list">
      {#each projects as project (project.id)}
        <li>
          {#if isProjectId(project.id)}
            <a href={`/projects/${project.id}`}>{project.id}</a>
          {:else}
            <span>{project.id}</span>
          {/if}
          <span class="date">{dateOf(project.modified)}</span>
        </li>
      {/each}
    </ul>
  {/if}

  <form onsubmit={create}>
    <label for="new-project">New project</label>
    <input id="new-project" type="text" autocomplete="off" spellcheck="false" bind:value={name} />
    <button type="submit" disabled={creating}>Create</button>
    {#if createError}
      <p class="problem" role="alert">{createError}</p>
    {/if}
  </form>
{/if}

<style>
  .workspace { color: #555; font-size: 0.85rem; margin: 0 0 1rem; }
  .empty { font-size: 1.1rem; }
  .list { list-style: none; padding: 0; margin: 0 0 1.5rem; }
  .list li { display: flex; justify-content: space-between; border-top: 1px solid #d8d8d8; padding: 0.5rem 0; max-width: 32rem; }
  .date { color: #555; }
  form { margin-top: 1rem; }
  input { padding: 0.35rem; margin: 0 0.5rem; }
  .problem { color: #a11; }
</style>
