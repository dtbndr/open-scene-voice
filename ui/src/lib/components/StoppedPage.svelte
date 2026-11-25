<script lang="ts">
  let copied = $state(false);

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText('scenevoice web');
      copied = true;
    } catch {
      copied = false; // the command stays visible as text below
    }
  }
</script>

<main class="notice">
  <h1>SceneVoice has stopped.</h1>
  <p>The Terminal window was probably closed. Your work is saved in the SceneVoice folder in your Documents folder.</p>
  <p>To carry on: open Terminal, type <code>scenevoice web</code> and press Return.</p>
  <p>
    <button type="button" onclick={copy}>Copy the command</button>
    {#if copied}<span role="status">Copied.</span>{/if}
  </p>
</main>

<style>
  .notice {
    max-width: 38rem;
    margin: 4rem auto;
    padding: 1.5rem;
    border: 1px solid #c9c9c9;
    border-radius: 0.5rem;
    background: #fffaf0;
    color: #222;
  }
  h1 {
    margin-top: 0;
    font-size: 1.4rem;
  }
  code {
    padding: 0.1rem 0.35rem;
    background: #eee;
    border-radius: 0.25rem;
  }
  button {
    font: inherit;
    padding: 0.4rem 0.9rem;
  }
</style>
