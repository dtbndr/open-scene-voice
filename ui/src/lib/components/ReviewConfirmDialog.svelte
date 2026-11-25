<script lang="ts">
  // The one-scene redo confirmation: the replace sentence and the recorded settings, read-only. Only its confirm button posts.
  import type { Snapshot } from '$lib/api/confirm';
  import type { AudioSettings } from '$lib/api/types';
  import { REVIEW_WORDS, replaceLine, settingsLine } from '$lib/voice/review';

  let {
    open,
    snapshot,
    settings,
    onconfirm,
    ondismiss
  }: { open: boolean; snapshot: Snapshot | null; settings: AudioSettings | null | undefined; onconfirm: () => void; ondismiss: () => void } = $props();
  let dialog = $state<HTMLDialogElement>();

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
  <h2>{REVIEW_WORDS.confirmTitle}</h2>
  {#if snapshot?.scene}
    <p>{replaceLine(snapshot.scene)}</p>
  {/if}
  <p>{settingsLine(settings)}</p>
  {#if settings?.language}<p>Language: {settings.language}</p>{/if}
  {#if settings?.instruction}<p>Delivery style: {settings.instruction}</p>{/if}
  <p>{REVIEW_WORDS.confirmQuota}</p>
  <div class="buttons">
    <button type="button" onclick={ondismiss}>{REVIEW_WORDS.back}</button>
    <button type="button" onclick={onconfirm} disabled={snapshot === null}>{REVIEW_WORDS.confirm}</button>
  </div>
</dialog>

<style>
  dialog { border: 1px solid #999; border-radius: 6px; padding: 1.25rem; max-width: 30rem; }
  h2 { margin-top: 0; font-size: 1.1rem; }
  .buttons { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
</style>
