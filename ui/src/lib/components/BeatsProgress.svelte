<script lang="ts">
  let { cancelling, canCancel = true, oncancel }: { cancelling: boolean; canCancel?: boolean; oncancel: () => void } = $props();
</script>

<p><strong>Planning visual beats...</strong></p>
<p>This can take a minute. Keep the Terminal window open. A cancelled request may still be charged.</p>
{#if canCancel}
  <button type="button" onclick={oncancel} disabled={cancelling}>{cancelling ? 'Stopping...' : 'Cancel'}</button>
{/if}
