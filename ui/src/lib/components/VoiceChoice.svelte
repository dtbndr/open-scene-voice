<script lang="ts">
  // Screen 5: provider, voice, language, delivery style, the cost line and "Next: Generate". All strings are in
  // VOICE_WORDS (proposed wording). With `locked` (voice the rest) the settings are shown read-only from the record.
  import type { AudioSettings, Catalog } from '$lib/api/types';
  import { MODEL_LABELS, VOICE_WORDS, costLine, providerOf, radioModels, type VoiceMode } from '$lib/voice/flow';
  import type { VoiceModel } from '$lib/voice/voice.svelte';

  let {
    catalog,
    model,
    locked,
    modes,
    cost,
    canPress,
    busy,
    unavailable,
    onpress
  }: {
    catalog: Catalog;
    model: VoiceModel;
    locked: AudioSettings | null;
    modes: VoiceMode[];
    cost: { scenes: number; characters: number } | null;
    canPress: boolean;
    busy: boolean;
    unavailable: boolean;
    onpress: () => void;
  } = $props();

  const radios = $derived(radioModels(catalog));
  const spec = $derived(providerOf(catalog, model.modelId));
  const pasted = $derived(spec !== null && spec.voices === null);
  const lockedModel = $derived(locked?.model ? (MODEL_LABELS[locked.model] ?? locked.model) : '');
</script>

<h1>{VOICE_WORDS.title}</h1>

{#if modes.length > 1}
  <div role="radiogroup" aria-label="What to do">
    {#each modes as option (option)}
      <label>
        <input type="radio" name="voice-mode" value={option} checked={model.mode === option} onchange={() => (model.mode = option)} />
        {option === 'rest' ? VOICE_WORDS.modeRest : VOICE_WORDS.modeRestart}
      </label>
    {/each}
  </div>
{/if}

{#if locked}
  <p>{VOICE_WORDS.restNote}</p>
  <dl class="settings">
    <dt>{VOICE_WORDS.provider}</dt>
    <dd>{lockedModel}</dd>
    <dt>{VOICE_WORDS.voice}</dt>
    <dd>{locked.voice ?? ''}</dd>
    {#if locked.language}
      <dt>{VOICE_WORDS.language}</dt>
      <dd>{locked.language}</dd>
    {/if}
    {#if locked.instruction}
      <dt>{VOICE_WORDS.style}</dt>
      <dd>{locked.instruction}</dd>
    {/if}
  </dl>
{:else}
  <fieldset>
    <legend>{VOICE_WORDS.provider}</legend>
    {#each radios as radio (radio.id)}
      <label>
        <input type="radio" name="voice-model" value={radio.id} bind:group={model.modelId} />
        {radio.label}
      </label>
    {/each}
  </fieldset>

  <div class="field">
    {#if pasted}
      <label for="voice-id">{VOICE_WORDS.voiceId}</label>
      <input id="voice-id" type="text" autocomplete="off" spellcheck="false" maxlength="1000" bind:value={model.pastedVoiceId} />
      <p class="hint">{VOICE_WORDS.voiceIdHint}</p>
    {:else}
      <label for="voice-name">{VOICE_WORDS.voice}</label>
      <select id="voice-name" bind:value={model.geminiVoice}>
        {#each spec?.voices ?? [] as name (name)}
          <option value={name}>{name}</option>
        {/each}
      </select>
      <label for="voice-language">{VOICE_WORDS.language}</label>
      <input id="voice-language" type="text" autocomplete="off" spellcheck="false" maxlength="1000" bind:value={model.language} />
      <label for="voice-style">{VOICE_WORDS.style}</label>
      <input
        id="voice-style"
        type="text"
        autocomplete="off"
        maxlength="1000"
        placeholder={VOICE_WORDS.stylePlaceholder}
        bind:value={model.style}
      />
    {/if}
  </div>
{/if}

{#if unavailable}
  <p class="problem" role="status">{VOICE_WORDS.unavailable}</p>
{:else if cost}
  <p>{costLine(cost.scenes, cost.characters)}</p>
{/if}
{#if busy}
  <p role="status">{VOICE_WORDS.busy}</p>
{/if}
<button type="button" onclick={onpress} disabled={!canPress}>{VOICE_WORDS.next}</button>

<style>
  .problem { color: #a11; }
  fieldset { border: 0; padding: 0; margin: 0.75rem 0; }
  fieldset label, [role='radiogroup'] label { display: block; margin: 0.25rem 0; }
  .field { display: grid; grid-template-columns: 8rem 1fr; gap: 0.5rem; align-items: center; margin: 0.75rem 0; max-width: 40rem; }
  .field input, .field select { padding: 0.35rem; }
  .hint { grid-column: 2; margin: 0; font-size: 0.9rem; }
  .settings { display: grid; grid-template-columns: 8rem 1fr; gap: 0.25rem 0.5rem; max-width: 40rem; }
  .settings dd { margin: 0; }
</style>
