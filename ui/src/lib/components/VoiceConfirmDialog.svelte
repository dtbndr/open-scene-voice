<script lang="ts">
  // The confirmation for one paid voicing job. The page opens it by phase; only its own confirm button posts.
  // All strings are in CONFIRM_WORDS (proposed wording).
  import type { Snapshot } from '$lib/api/confirm';
  import { CONFIRM_WORDS, confirmSummary, voiceButton } from '$lib/voice/flow';

  let { open, snapshot, onconfirm, ondismiss }: { open: boolean; snapshot: Snapshot | null; onconfirm: () => void; ondismiss: () => void } = $props();
  let dialog = $state<HTMLDialogElement>();
  const scenes = $derived(snapshot?.scenes ?? 0);

  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  });
</script>

<dialog
  bind:this={dialog}
  oncancel={(event) => {
    event.preventDefault();
    ondismiss();
  }}
>
  <h2>{CONFIRM_WORDS.title}</h2>
  {#if snapshot}
    <p>{confirmSummary(scenes, snapshot.characters ?? 0, snapshot.model)}</p>
  {/if}
  <p>{CONFIRM_WORDS.quota}</p>
  <div class="buttons">
    <button type="button" onclick={ondismiss}>{CONFIRM_WORDS.back}</button>
    <button type="button" onclick={onconfirm} disabled={snapshot === null}>{voiceButton(scenes)}</button>
  </div>
</dialog>

<style>
  dialog { border: 1px solid #999; border-radius: 6px; padding: 1.25rem; max-width: 30rem; }
  h2 { margin-top: 0; font-size: 1.1rem; }
  .buttons { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
</style>
