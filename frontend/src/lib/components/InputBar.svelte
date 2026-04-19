<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let value = '';
  export let disabled = false;

  const dispatch = createEventDispatcher<{
    submit: { url: string };
    focus: void;
    blur: void;
  }>();

  function submit() {
    const trimmed = value.trim();
    if (!trimmed) return;
    dispatch('submit', { url: trimmed });
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter') submit();
  }
</script>

<div class="bar">
  <input
    type="url"
    placeholder="Spotify-, Deezer- oder Tidal-Link einfügen …"
    bind:value
    on:keydown={onKeyDown}
    on:focus={() => dispatch('focus')}
    on:blur={() => dispatch('blur')}
    aria-label="Streaming-Link"
    {disabled}
  />
  <button type="button" on:click={submit} {disabled}>Konvertieren</button>
</div>

<style>
  .bar {
    display: flex;
    gap: 0.5rem;
    align-items: stretch;
  }
  input {
    flex: 1;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    background: var(--bg-surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  button {
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    padding: 0 1.25rem;
    cursor: pointer;
    font-weight: 600;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
