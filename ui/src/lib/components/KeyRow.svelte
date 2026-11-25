<script lang="ts">
  import type { KeyName } from '$lib/api/types';
  import type { KeysModel } from '$lib/keys.svelte';

  let { model, name, label, note = '' }: { model: KeysModel; name: KeyName; label: string; note?: string } = $props();

  const field = $derived(model.fields[name]);
  const failure = $derived(model.error?.name === name ? model.error.message : null);
  let justSaved = $state(false);

  async function save() {
    justSaved = false;
    const result = await model.save([name]);
    justSaved = result.ok;
  }

  async function remove() {
    justSaved = false;
    await model.remove(name);
  }
</script>

<section class="row">
  <div class="head">
    <h2>{label}</h2>
    <span class="status">{field.saved ? 'Saved' : 'Not added'}</span>
  </div>
  {#if note}<p class="note">{note}</p>{/if}
  <div class="controls">
    <label>
      <span class="visually-hidden">{field.saved ? 'Replace key' : 'Paste key'}</span>
      <input
        type="password"
        autocomplete="off"
        spellcheck="false"
        placeholder={field.saved ? 'Replace...' : 'Paste key...'}
        bind:value={field.input}
      />
    </label>
    <button type="button" onclick={save} disabled={model.busy || field.input.trim() === ''}>Save</button>
    {#if field.saved}
      <button type="button" onclick={remove} disabled={model.busy}>Remove</button>
    {/if}
  </div>
  <p class="message" role="status">{justSaved ? 'Saved.' : ''}</p>
  {#if failure}<p class="problem" role="alert">{failure}</p>{/if}
</section>

<style>
  .row { border-top: 1px solid #d8d8d8; padding: 0.75rem 0; }
  .head { display: flex; justify-content: space-between; align-items: baseline; }
  h2 { font-size: 1rem; margin: 0; }
  .status { color: #555; }
  .note { margin: 0.25rem 0; color: #555; font-size: 0.9rem; }
  .controls { display: flex; gap: 0.5rem; margin-top: 0.5rem; }
  input { width: 22rem; max-width: 100%; padding: 0.35rem; }
  .message { margin: 0.25rem 0 0; min-height: 1.2em; color: #1a6b2f; }
  .problem { margin: 0.25rem 0 0; color: #a11; }
  .visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
</style>
