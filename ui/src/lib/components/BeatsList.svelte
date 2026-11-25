<script lang="ts">
  import { rangeWords, type BeatsScene } from '$lib/beats/guard';

  let { scenes }: { scenes: BeatsScene[] } = $props();
</script>

<ol class="scenes">
  {#each scenes as scene, position (position)}
    <li>
      <h3>Scene {scene.ordinal}: {scene.title}</h3>
      <ul>
        {#each scene.beats as beat, index (index)}
          <li><strong>{rangeWords(beat.first, beat.last)}</strong>: {beat.note}</li>
        {/each}
      </ul>
    </li>
  {/each}
</ol>

<style>
  .scenes { list-style: none; padding: 0; }
  h3 { margin: 0.75rem 0 0.25rem; font-size: 1rem; }
</style>
