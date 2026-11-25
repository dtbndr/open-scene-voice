<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import KeyRow from '$lib/components/KeyRow.svelte';
  import { firstLaunch } from '$lib/first-launch.svelte';
  import { KeysModel } from '$lib/keys.svelte';
  import type { KeyName } from '$lib/api/types';

  const model = new KeysModel();
  const key = model.fields.VERTEX_AUTHORIZATION_KEY;
  const project = model.fields.GOOGLE_CLOUD_PROJECT;
  const region = model.fields.GOOGLE_CLOUD_LOCATION;

  const GOOGLE_LABELS: Record<string, string> = {
    VERTEX_AUTHORIZATION_KEY: 'the key',
    GOOGLE_CLOUD_PROJECT: 'the project ID',
    GOOGLE_CLOUD_LOCATION: 'the region'
  };
  const googleMissing = $derived(
    (['VERTEX_AUTHORIZATION_KEY', 'GOOGLE_CLOUD_PROJECT', 'GOOGLE_CLOUD_LOCATION'] as KeyName[]).filter(
      (name) => !model.fields[name].saved
    )
  );
  const googleNames = $derived(model.googleNames());
  const googleFailure = $derived(
    model.error && model.error.name in GOOGLE_LABELS ? model.error : null
  );
  let googleSaved = $state(false);

  onMount(() => {
    model.load();
  });

  async function saveGoogle() {
    googleSaved = false;
    const result = await model.save(model.googleNames());
    googleSaved = result.ok;
  }

  function listNames(names: string[]): string {
    return names.map((name) => GOOGLE_LABELS[name]).join(', ');
  }
</script>

<div class="top">
  <h1>Keys</h1>
  {#if firstLaunch.value}
    <button type="button" onclick={() => goto('/')}>Skip for now</button>
  {/if}
</div>
<p>Your keys stay on this computer. SceneVoice never shows a saved key back.</p>

{#if model.loadError}
  <p class="problem" role="alert">{model.loadError}</p>
{:else if !model.loaded}
  <p>Loading...</p>
{:else}
  {#each model.ignored as name (name)}
    <p class="notice">Your Terminal sets {name}, which SceneVoice ignores here. Only keys saved on this page are used.</p>
  {/each}

  <section class="row">
    <div class="head">
      <h2>Google Cloud (Gemini voices)</h2>
      <span class="status">{googleMissing.length === 0 ? 'Saved' : 'Not added'}</span>
    </div>
    {#if googleMissing.length > 0 && googleMissing.length < 3}
      <p class="note">Missing: {listNames(googleMissing)}.</p>
    {/if}
    <div class="grid">
      <label for="google-key">Key</label>
      <input
        id="google-key"
        type="password"
        autocomplete="off"
        spellcheck="false"
        placeholder={key.saved ? 'Replace...' : 'Paste key...'}
        bind:value={key.input}
      />
      <label for="google-project">Project ID</label>
      <input
        id="google-project"
        type="text"
        autocomplete="off"
        spellcheck="false"
        placeholder="Your Google Cloud project"
        bind:value={project.input}
      />
      <label for="google-region">Region</label>
      <input
        id="google-region"
        type="text"
        autocomplete="off"
        spellcheck="false"
        placeholder="Suggested region"
        bind:value={region.input}
      />
    </div>
    <div class="controls">
      <button type="button" onclick={saveGoogle} disabled={model.busy || googleNames.length === 0}>Save</button>
    </div>
    <p class="message" role="status">{googleSaved ? 'Saved.' : ''}</p>
    {#if googleFailure}
      <p class="problem" role="alert">
        Not saved: {GOOGLE_LABELS[googleFailure.name]}. {googleFailure.message}
      </p>
    {/if}
  </section>

  <KeyRow {model} name="ELEVENLABS_API_KEY" label="ElevenLabs voices" />
  <KeyRow {model} name="OPENROUTER_API_KEY" label="OpenRouter (line markers and scene beats)" />

  <h2>Which do I need?</h2>
  <ul>
    <li>Gemini voices need the Google Cloud key, project ID and region.</li>
    <li>ElevenLabs voices need the ElevenLabs key.</li>
    <li>Line markers for Gemini voices need the OpenRouter key.</li>
    <li>Scene and visual beats need the OpenRouter key.</li>
  </ul>
{/if}

<style>
  .top { display: flex; justify-content: space-between; align-items: center; }
  .row { border-top: 1px solid #d8d8d8; padding: 0.75rem 0; }
  .head { display: flex; justify-content: space-between; align-items: baseline; }
  h2 { font-size: 1rem; margin: 0.5rem 0 0; }
  .head h2 { margin: 0; }
  .status, .note { color: #555; }
  .note { margin: 0.25rem 0; font-size: 0.9rem; }
  .grid { display: grid; grid-template-columns: 6rem 22rem; gap: 0.5rem; align-items: center; margin-top: 0.5rem; }
  .grid input { padding: 0.35rem; }
  .controls { margin-top: 0.5rem; }
  .message { margin: 0.25rem 0 0; min-height: 1.2em; color: #1a6b2f; }
  .problem { color: #a11; }
  .notice { background: #fff6dd; padding: 0.5rem 0.75rem; border-radius: 4px; }
</style>
