<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte';
  import { history, clearHistory } from '$lib/stores/history';

  export let open = false;

  const dispatch = createEventDispatcher<{ select: { url: string }; close: void }>();

  let activeIndex = 0;
  let itemButtons: HTMLButtonElement[] = [];

  // Keep activeIndex within bounds when the history list shrinks. When the
  // dropdown closes, reset to 0 so the next open starts fresh.
  $: if (!open) {
    activeIndex = 0;
  } else if (activeIndex >= $history.length) {
    activeIndex = Math.max(0, $history.length - 1);
  }

  async function focusActive() {
    await tick();
    itemButtons[activeIndex]?.focus();
  }

  function handleKey(event: KeyboardEvent) {
    const len = $history.length;
    if (event.key === 'Escape') {
      event.preventDefault();
      dispatch('close');
      return;
    }
    if (!len) return;
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        activeIndex = (activeIndex + 1) % len;
        focusActive();
        break;
      case 'ArrowUp':
        event.preventDefault();
        activeIndex = (activeIndex - 1 + len) % len;
        focusActive();
        break;
      case 'Home':
        event.preventDefault();
        activeIndex = 0;
        focusActive();
        break;
      case 'End':
        event.preventDefault();
        activeIndex = len - 1;
        focusActive();
        break;
    }
  }

  function select(url: string) {
    dispatch('select', { url });
  }

  function truncate(url: string, n = 40) {
    return url.length > n ? url.slice(0, n - 1) + '…' : url;
  }
</script>

{#if open && $history.length > 0}
  <div
    class="dropdown"
    role="listbox"
    aria-label="Verlauf"
    tabindex="-1"
    on:keydown={handleKey}
  >
    <div class="hint">Zuletzt:</div>
    {#each $history as entry, i (entry.sourceUrl)}
      <button
        bind:this={itemButtons[i]}
        type="button"
        class="item"
        role="option"
        aria-label={entry.title}
        aria-selected={activeIndex === i}
        tabindex={activeIndex === i ? 0 : -1}
        on:click={() => select(entry.sourceUrl)}
      >
        <span class="title">{entry.title}</span>
        {#if entry.artists.length}<span class="artists">— {entry.artists.join(', ')}</span>{/if}
        <span class="url">{truncate(entry.sourceUrl)}</span>
      </button>
    {/each}
    <div class="footer">
      <button type="button" class="clear" on:click={clearHistory}>Verlauf leeren</button>
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
  .item:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .title { font-weight: 600; }
  .artists { color: var(--text-muted); }
  .url { color: var(--text-muted); font-size: 0.8rem; margin-left: auto; }
  .footer { border-top: 1px solid var(--border); padding-top: 0.25rem; margin-top: 0.25rem; text-align: right; }
  .clear { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.8rem; }
  .clear:hover { color: var(--error); }
</style>
