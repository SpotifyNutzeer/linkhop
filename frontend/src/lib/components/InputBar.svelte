<script lang="ts">
  interface Props {
    value?: string;
    disabled?: boolean;
    onsubmit?: (detail: { url: string }) => void;
    onfocus?: () => void;
    onblur?: () => void;
  }

  let {
    value = $bindable(''),
    disabled = false,
    onsubmit,
    onfocus,
    onblur
  }: Props = $props();

  function submit() {
    const trimmed = value.trim();
    if (!trimmed) return;
    onsubmit?.({ url: trimmed });
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
    placeholder="Spotify-, Deezer-, Tidal-, YouTube-Music- oder Apple-Music-Link einfügen …"
    bind:value
    onkeydown={onKeyDown}
    onfocus={() => onfocus?.()}
    onblur={() => onblur?.()}
    aria-label="Streaming-Link"
    {disabled}
  />
  <button type="button" class="go" onclick={submit} {disabled}>Konvertieren</button>
</div>

<style>
  /* Input/Select-Rezept: surface0, kein Border, radius 10, Fokus = Teal-
     Ring statt Border-Farbwechsel + Lift. */
  .bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.4rem 0.4rem 1rem;
    background: var(--surface0);
    border-radius: var(--r-md);
    transition: box-shadow var(--dur-fast) var(--ease-out);
  }
  .bar:focus-within {
    box-shadow: 0 0 0 2px var(--accent);
  }
  .bar.is-disabled { opacity: 0.75; }
  .lead {
    color: var(--text-dim);
    display: inline-flex;
    transition: color var(--dur-fast) var(--ease-out);
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
    border: 0;
    border-radius: var(--r-md);
    background: var(--accent);
    color: var(--accent-contrast);
    font: inherit;
    font-weight: 700;
    font-size: 0.92rem;
    letter-spacing: 0.01em;
    cursor: pointer;
    transition: filter var(--dur-fast) var(--ease-out);
  }
  .go:not(:disabled):hover { filter: brightness(1.12); }
  .go:not(:disabled):active { filter: brightness(0.95); }
  .go:disabled { opacity: 0.55; cursor: not-allowed; }

  @media (max-width: 520px) {
    .bar { padding: 0.4rem 0.4rem 0.4rem 0.85rem; gap: 0.35rem; }
    .go { padding: 0.6rem 0.9rem; font-size: 0.88rem; }
  }
</style>
