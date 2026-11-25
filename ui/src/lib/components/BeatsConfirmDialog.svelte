<script lang="ts">
  // The confirmation for one paid beats request. The page opens it by phase; only its own confirm button posts.
  let { open, onconfirm, ondismiss }: { open: boolean; onconfirm: () => void; ondismiss: () => void } = $props();
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
  <h2>Plan visual beats for this script?</h2>
  <p>
    This is one paid request to your OpenRouter account. Your script text is sent to OpenRouter and on to the model
    provider. The answer has a limit on its length. No price is shown. A cancelled request may still be charged.
  </p>
  <div class="buttons">
    <button type="button" onclick={ondismiss}>Back</button>
    <button type="button" onclick={onconfirm}>Plan visual beats</button>
  </div>
</dialog>

<style>
  dialog { border: 1px solid #999; border-radius: 6px; padding: 1.25rem; max-width: 30rem; }
  h2 { margin-top: 0; font-size: 1.1rem; }
  .buttons { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem; }
</style>
