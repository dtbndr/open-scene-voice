<script lang="ts">
  // The paid confirmation for updating line markers. The page opens it by phase; only its own confirm button posts.
  import type { Snapshot } from '$lib/api/confirm';
  import { PACK_WORDS, confirmSentence } from '$lib/pack/words';

  let { open, snapshot, onconfirm, ondismiss }: { open: boolean; snapshot: Snapshot | null; onconfirm: () => void; ondismiss: () => void } = $props();
  let dialog = $state<HTMLDialogElement>();

  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  });
</script>

<dialog
  bind:this={dialog}
  aria-label={PACK_WORDS.updateButton}
  oncancel={(event) => {
    event.preventDefault();
    ondismiss();
  }}
>
  {#if snapshot}
    <p>{confirmSentence(snapshot.scenes ?? 0)}</p>
  {/if}
  <div class="buttons">
    <button type="button" onclick={ondismiss}>{PACK_WORDS.back}</button>
    <button type="button" onclick={onconfirm} disabled={snapshot === null}>{PACK_WORDS.updateButton}</button>
  </div>
</dialog>

<style>
  dialog { border: 1px solid #999; border-radius: 6px; padding: 1.25rem; max-width: 30rem; }
  .buttons { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
</style>
