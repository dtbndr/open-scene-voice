<script lang="ts">
  import { beforeNavigate } from '$app/navigation';
  import { page } from '$app/state';
  import { api } from '$lib/api/client';
  import { ApiError, FIXED_MESSAGE, NetworkError } from '$lib/api/errors';
  import type { ProjectDetail } from '$lib/api/types';
  import { jobs } from '$lib/app.svelte';
  import ScriptEditor from '$lib/components/ScriptEditor.svelte';
  import { ScriptModel } from '$lib/script/script.svelte';

  const LEAVE_QUESTION = 'You have changes that are not saved. Leave without saving?';

  const id = $derived(page.params.id ?? '');
  let detail = $state.raw<ProjectDetail | null>(null);
  let script = $state.raw<ScriptModel | null>(null);
  let problem = $state<string | null>(null);

  // Any beats button reads these: the box equals the saved text, nothing is wrong in it, and the saved file allows it.
  const beatsOffered = $derived(
    script !== null &&
      script.loaded &&
      !script.dirty &&
      script.check?.ok === true &&
      !script.greyed &&
      (detail?.can?.beats === true || detail?.can?.beats_redo === true)
  );

  function words(error: unknown): string {
    return error instanceof ApiError || error instanceof NetworkError ? error.message : FIXED_MESSAGE;
  }

  async function refresh(forId: string): Promise<void> {
    const fresh = await api.project(forId);
    if (forId === id) detail = fresh;
  }

  // The project follows the address: a new id starts a new model and a new load.
  $effect(() => {
    const current = id;
    const model = new ScriptModel(current, { jobActive: () => jobs.active, reread: () => refresh(current) });
    let alive = true;
    // A finished job changes what the project allows: re-read the detail (the beats page registers its own listener).
    const stopListening = jobs.listen(async (project) => {
      if (alive && (project === null || project === current)) await refresh(current);
    });
    script = model;
    detail = null;
    problem = null;
    (async () => {
      try {
        const first = await api.project(current);
        if (!alive) return;
        detail = first;
        await model.load();
      } catch (error) {
        if (alive) problem = words(error);
      }
    })();
    return () => {
      alive = false;
      stopListening();
      model.dispose();
    };
  });

  beforeNavigate((navigation) => {
    if (!script?.dirty) return;
    if (navigation.type === 'leave') navigation.cancel(); // closing the tab: the browser asks
    else if (!window.confirm(LEAVE_QUESTION)) navigation.cancel();
  });
</script>

<p><a href="/">Back to Projects</a> <span class="id">{id}</span></p>

{#if problem}
  <p class="problem" role="alert">{problem}</p>
{:else if script?.loadError}
  <p class="problem" role="alert">{script.loadError}</p>
{:else if !script || !script.loaded || !detail}
  <p>Loading...</p>
{:else}
  <ScriptEditor model={script} {id} />
  {#if beatsOffered}
    <p class="beats"><a href={`/projects/${encodeURIComponent(id)}/beats`}>Plan visual beats</a></p>
  {/if}
{/if}

<style>
  .problem { color: #a11; }
  .id { color: #555; margin-left: 1rem; }
  .beats { margin-top: 1rem; }
</style>
