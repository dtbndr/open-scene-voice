<script lang="ts">
  import { lineRange } from '$lib/script/pure';
  import type { ScriptModel } from '$lib/script/script.svelte';
  import NextVoice from './NextVoice.svelte';
  import ProblemList from './ProblemList.svelte';

  let { model, id }: { model: ScriptModel; id: string } = $props();

  let box = $state<HTMLTextAreaElement>();
  let picker = $state<HTMLInputElement>();

  const empty = $derived(model.text.trim() === '');
  // Saved, with a check answer that found no problem; a failed or missing check never counts as clean.
  const voiceReady = $derived(!empty && !model.dirty && !model.greyed && model.check?.ok === true);
  const indicator = $derived(
    model.justSaved ? 'Saved' : model.dirty ? 'Changes not saved' : model.text !== '' ? 'Saved' : ''
  );

  async function chosen() {
    const file = picker?.files?.[0];
    if (file) await model.upload(file);
    if (picker) picker.value = ''; // so the same file can be chosen again
  }

  /** Pixel offset of the top of the line starting at `start`, measured on an off-screen copy of the box. */
  function offsetOf(area: HTMLTextAreaElement, start: number): number {
    const style = getComputedStyle(area);
    const top = parseFloat(style.paddingTop);
    if (start === 0) return top;
    const probe = area.cloneNode(false) as HTMLTextAreaElement;
    probe.removeAttribute('id');
    probe.value = area.value.slice(0, start - 1);
    Object.assign(probe.style, {
      position: 'absolute',
      visibility: 'hidden',
      left: '-9999px',
      height: '0',
      minHeight: '0',
      maxHeight: 'none',
      boxSizing: 'content-box',
      overflow: 'hidden',
      width: `${area.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)}px`
    });
    area.parentElement?.appendChild(probe);
    const above = probe.scrollHeight - parseFloat(style.paddingBottom);
    probe.remove();
    return above;
  }

  /** Select line `line` of the text in the box and scroll it into view. */
  function showLine(line: number): void {
    if (!box) return;
    const { start, end } = lineRange(box.value, line);
    box.focus();
    box.setSelectionRange(start, end);
    box.scrollTop = Math.max(0, offsetOf(box, start) - box.clientHeight / 3);
  }
</script>

<div class="head">
  <h1>Script <span class="file">script.md</span></h1>
  <div class="controls">
    <input
      bind:this={picker}
      type="file"
      accept=".md,.markdown,.txt,text/plain,text/markdown"
      hidden
      onchange={chosen}
    />
    <button type="button" onclick={() => picker?.click()}>Upload file</button>
    <button type="button" onclick={() => model.save()} disabled={model.greyed || !model.dirty}>Save</button>
    <span class="indicator" role="status">{indicator}</span>
  </div>
</div>

{#if empty}
  <p class="hint">
    Paste your script here or upload a file. New to the format?
    <a href="/guide" target="_blank" rel="noopener">Read the script guide</a>.
  </p>
{/if}
{#if model.note}
  <p class="notice">{model.note}</p>
{/if}
{#if model.uploadError}
  <p class="problem" role="alert">{model.uploadError}</p>
{/if}
{#if model.saveError}
  <p class="problem" role="alert">{model.saveError}</p>
{/if}

<textarea
  bind:this={box}
  aria-label="Script text"
  rows="20"
  value={model.text}
  oninput={(event) => model.edit(event.currentTarget.value)}
></textarea>

<ProblemList
  check={model.check}
  checkError={model.checkError}
  checking={model.checking}
  {empty}
  onShowLine={showLine}
/>

<NextVoice {id} enabled={voiceReady} />

<style>
  .head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem; }
  .file { font-weight: normal; color: #555; font-size: 1rem; margin-left: 0.5rem; }
  .controls { display: flex; gap: 0.75rem; align-items: center; }
  .indicator { color: #1a6b2f; min-width: 8rem; }
  textarea {
    width: 100%;
    box-sizing: border-box;
    height: 28rem;
    padding: 0.5rem;
    font: 0.95rem/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
    resize: vertical;
  }
  .hint { color: #555; }
  .problem { color: #a11; }
  .notice { background: #fff6dd; padding: 0.5rem 0.75rem; border-radius: 4px; }
</style>
