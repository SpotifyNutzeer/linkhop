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

<div class="bar" class:is-disabled={disabled}>
  <span class="lead" aria-hidden="true">
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor"
         stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="11" cy="11" r="7" />
      <line x1="16.2" y1="16.2" x2="21" y2="21" />
    </svg>
  </span>
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
  <button type="button" class="go" on:click={submit} {disabled}>Konvertieren</button>
</div>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.4rem 0.4rem 1rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-pill);
    backdrop-filter: blur(28px) saturate(180%);
    -webkit-backdrop-filter: blur(28px) saturate(180%);
    box-shadow: var(--glass-shadow);
    transition: border-color var(--dur) var(--ease-out),
                transform var(--dur) var(--ease-spring);
  }
  .bar:focus-within {
    border-color: var(--accent);
    transform: translateY(-1px);
  }
  .bar.is-disabled { opacity: 0.75; }
  .lead {
    color: var(--text-dim);
    display: inline-flex;
    transition: color var(--dur) var(--ease-out);
  }
  .bar:focus-within .lead { color: var(--accent); }
  input {
    flex: 1;
    min-width: 0;
    padding: 0.65rem 0.25rem;
    font: inherit;
    font-size: 1rem;
    color: var(--text);
    background: transparent;
    border: none;
    outline: none;
  }
  input::placeholder { color: var(--text-dim); }
  .go {
    flex-shrink: 0;
    padding: 0.65rem 1.1rem;
    border: 1px solid transparent;
    border-radius: var(--r-pill);
    background: var(--accent);
    color: var(--accent-contrast);
    font: inherit;
    font-weight: 600;
    font-size: 0.92rem;
    letter-spacing: 0.01em;
    cursor: pointer;
    box-shadow:
      0 1px 0 0 rgba(255, 255, 255, 0.35) inset,
      0 -1px 0 0 rgba(0, 0, 0, 0.18) inset,
      0 6px 18px -8px rgba(0, 0, 0, 0.4);
    transition: transform var(--dur-fast) var(--ease-spring),
                filter var(--dur-fast) var(--ease-out);
  }
  .go:not(:disabled):hover { filter: brightness(1.06); transform: translateY(-1px); }
  .go:not(:disabled):active { transform: translateY(0); filter: brightness(0.95); }
  .go:disabled { opacity: 0.55; cursor: not-allowed; }

  @media (max-width: 520px) {
    .bar { padding: 0.4rem 0.4rem 0.4rem 0.85rem; gap: 0.35rem; }
    .go { padding: 0.6rem 0.9rem; font-size: 0.88rem; }
  }
</style>
