<script lang="ts">
  let {
    model = $bindable(),
    withinLimit,
    canPress,
    redoing,
    onpress
  }: { model: string; withinLimit: boolean; canPress: boolean; redoing: boolean; onpress: () => void } = $props();
</script>

<div class="field">
  <label for="beats-model">Model</label>
  <input
    id="beats-model"
    type="text"
    autocomplete="off"
    spellcheck="false"
    placeholder="Type or paste the OpenRouter model you want to use"
    bind:value={model}
  />
</div>
<p>
  This uses your OpenRouter quota. No price is shown. The length of the answer is limited. Your script text is sent to
  OpenRouter and on to the model provider.
</p>
{#if !withinLimit}
  <p class="problem">This script is longer than the 20,000-character limit for visual beats.</p>
{/if}
<button type="button" onclick={onpress} disabled={!canPress}>{redoing ? 'Redo beats' : 'Plan visual beats'}</button>

<style>
  .problem { color: #a11; }
  .field { display: grid; grid-template-columns: 5rem 1fr; gap: 0.5rem; align-items: center; margin: 0.75rem 0; max-width: 40rem; }
  .field input { padding: 0.35rem; }
</style>
