<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { history, clearHistory } from '$lib/stores/history';

  export let open = false;

  const dispatch = createEventDispatcher<{ select: { url: string } }>();

  function select(url: string) {
    dispatch('select', { url });
  }

  function truncate(url: string, n = 40) {
    return url.length > n ? url.slice(0, n - 1) + '…' : url;
  }
</script>

{#if open && $history.length > 0}
  <div class="dropdown" role="listbox" aria-label="Verlauf">
    <div class="hint">Zuletzt:</div>
    {#each $history as entry (entry.sourceUrl)}
      <button
        type="button"
        class="item"
        role="option"
        aria-label={entry.title}
        aria-selected="false"
        on:mousedown|preventDefault={() => select(entry.sourceUrl)}
        on:click={() => select(entry.sourceUrl)}
      >
        <span class="title">{entry.title}</span>
        {#if entry.artists.length}<span class="artists">— {entry.artists.join(', ')}</span>{/if}
        <span class="url">{truncate(entry.sourceUrl)}</span>
      </button>
    {/each}
    <div class="footer">
      <button type="button" class="clear" on:mousedown|preventDefault={clearHistory} on:click={clearHistory}>Verlauf leeren</button>
    </div>
  </div>
{/if}

<style>
  .dropdown {
    border: 1px solid var(--border);
    border-top: none;
    border-radius: 0 0 6px 6px;
    background: var(--bg-surface);
    padding: 0.5rem;
    max-height: 16rem;
    overflow-y: auto;
  }
  .hint { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.25rem; }
  .item {
    display: flex;
    gap: 0.5rem;
    background: transparent;
    border: none;
    color: var(--text);
    padding: 0.4rem 0.5rem;
    width: 100%;
    text-align: left;
    cursor: pointer;
    border-radius: 4px;
    align-items: baseline;
  }
  .item:hover { background: var(--bg); }
  .title { font-weight: 600; }
  .artists { color: var(--text-muted); }
  .url { color: var(--text-muted); font-size: 0.8rem; margin-left: auto; }
  .footer { border-top: 1px solid var(--border); padding-top: 0.25rem; margin-top: 0.25rem; text-align: right; }
  .clear { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.8rem; }
  .clear:hover { color: var(--error); }
</style>
