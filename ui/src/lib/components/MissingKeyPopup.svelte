<script lang="ts">
  import { onMount } from 'svelte';
  import type { KeyName } from '$lib/api/types';
  import { afterPartialSave, KeysModel, SEND_ORDER } from '$lib/keys.svelte';

  /** `missing`: key names to ask for (see `missingKeys`); `onsaved` runs once after every field saved. */
  let {
    missing,
    onsaved,
    oncancel
  }: { missing: KeyName[]; onsaved: () => void | Promise<void>; oncancel: () => void } = $props();

  const model = new KeysModel();
  let dialog = $state<HTMLDialogElement>();

  const ordered = $derived(SEND_ORDER.filter((name) => missing.includes(name)));
  // Names the server confirmed during this popup's life; a later try asks for and sends only the rest (item 15).
  let savedNames = $state.raw<KeyName[]>([]);
  const asking = $derived(afterPartialSave(ordered, savedNames).ask);
  const google = $derived(ordered.filter((name) => name.startsWith('GOOGLE') || name === 'VERTEX_AUTHORIZATION_KEY'));
  const title = $derived(
    google.length > 0
      ? 'This needs your Google Cloud details'
      : ordered.length === 1 && ordered[0] === 'ELEVENLABS_API_KEY'
        ? 'This needs your ElevenLabs key'
        : ordered.length === 1 && ordered[0] === 'OPENROUTER_API_KEY'
          ? 'This needs your OpenRouter key'
          : 'This needs a few more details'
  );
  const LABELS: Record<KeyName, string> = {
    VERTEX_AUTHORIZATION_KEY: 'Key',
    GOOGLE_CLOUD_PROJECT: 'Project ID',
    GOOGLE_CLOUD_LOCATION: 'Region',
    ELEVENLABS_API_KEY: 'ElevenLabs key',
    OPENROUTER_API_KEY: 'OpenRouter key'
  };
  const failure = $derived(model.error);
  let finished = false;
  let incomplete = $state(false);

  onMount(() => {
    dialog?.showModal();
    model.load();
  });

  async function saveAndContinue() {
    if (finished) return;
    incomplete = asking.some((name) => model.fields[name].input.trim() === '');
    if (incomplete) return;
    const result = await model.save(asking);
    savedNames = [...savedNames, ...result.saved];
    for (const name of afterPartialSave(asking, result.saved).clear) model.fields[name].input = '';
    if (!result.ok) return;
    finished = true;
    dialog?.close();
    await onsaved();
  }

  function cancel() {
    dialog?.close();
    oncancel();
  }
</script>

<dialog bind:this={dialog} aria-labelledby="missing-key-title" oncancel={(event) => { event.preventDefault(); cancel(); }}>
  <h2 id="missing-key-title">{title}</h2>
  {#if model.loaded}
    {#each asking as name (name)}
      {@const field = model.fields[name]}
      <div class="field">
        <label for={`popup-${name}`}>{LABELS[name]}</label>
        <input
          id={`popup-${name}`}
          type={field.secret ? 'password' : 'text'}
          autocomplete="off"
          spellcheck="false"
          bind:value={field.input}
        />
      </div>
    {/each}
  {:else if model.loadError}
    <p class="problem" role="alert">{model.loadError}</p>
  {:else}
    <p>Loading...</p>
  {/if}
  {#if incomplete}
    <p class="problem" role="alert">Fill in every field to continue.</p>
  {/if}
  {#if failure}
    <p class="problem" role="alert">Not saved: {LABELS[failure.name]}. {failure.message}</p>
  {/if}
  <div class="buttons">
    <button type="button" onclick={cancel}>Cancel</button>
    <button type="button" onclick={saveAndContinue} disabled={!model.loaded || model.busy}>Save and continue</button>
  </div>
</dialog>

<style>
  dialog { border: 1px solid #999; border-radius: 6px; padding: 1.25rem; max-width: 30rem; }
  h2 { margin-top: 0; font-size: 1.1rem; }
  .field { display: grid; grid-template-columns: 8rem 1fr; gap: 0.5rem; margin: 0.5rem 0; align-items: center; }
  .field input { padding: 0.35rem; }
  .buttons { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
  .problem { color: #a11; }
</style>
