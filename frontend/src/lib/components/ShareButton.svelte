<script lang="ts">
  import { onDestroy } from 'svelte';
  import { convert } from '$lib/api/client';
  import { ApiError } from '$lib/api/types';
  import { createCopyFeedback } from '$lib/stores/copyFeedback';

  interface Props {
    sourceUrl: string;
  }

  let { sourceUrl }: Props = $props();

  type Status = 'idle' | 'loading' | 'done' | 'error';

  let status: Status = $state('idle');
  let shortUrl = $state('');
  let shareError: ApiError | null = $state(null);
  let currentController: AbortController | null = null;

  const feedback = createCopyFeedback();
  const { copied, copyFailed } = feedback;

  async function share() {
    currentController?.abort();
    const ctrl = new AbortController();
    currentController = ctrl;
    status = 'loading';
    shareError = null;
    try {
      const res = await convert(sourceUrl, { share: true, signal: ctrl.signal });
      if (ctrl.signal.aborted) return;
      const info = res.share;
      if (!info?.id) {
        shareError = new ApiError('server_error', 0, 'Antwort ohne Share-ID', sourceUrl);
        status = 'error';
        return;
      }
      shortUrl = info.url ?? `${window.location.origin}/c/${info.id}`;
      status = 'done';
    } catch (e) {
      if (ctrl.signal.aborted || (e as DOMException).name === 'AbortError') return;
      shareError = e instanceof ApiError ? e : new ApiError('server_error', 0, String(e), sourceUrl);
      status = 'error';
    } finally {
      if (currentController === ctrl) {
        currentController = null;
      }
    }
  }

  async function copy() {
    if (!shortUrl) return;
    await feedback.copy(shortUrl);
  }

  onDestroy(() => {
    feedback.destroy();
    currentController?.abort();
  });
</script>

<div class="share">
  {#if status === 'idle'}
    <button type="button" class="primary" onclick={share}>Teilen</button>
  {:else if status === 'loading'}
    <button type="button" class="primary" disabled>
      <span class="spinner" aria-hidden="true"></span>
      Erzeuge Link …
    </button>
  {:else if status === 'done'}
    <code class="short">{shortUrl}</code>
    <button type="button" class="ghost" aria-label="Kurzlink kopieren" onclick={copy}>
      {#if $copyFailed}
        Fehlgeschlagen
      {:else if $copied}
        Kopiert
      {:else}
        Kopieren
      {/if}
    </button>
  {:else if status === 'error'}
    <span class="error">Fehler beim Erzeugen des Links</span>
    <button type="button" class="ghost" onclick={share}>Nochmal</button>
  {/if}
</div>

<style>
  .share {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 1rem;
  }
  /* Primär-Button-Rezept: teal-Bg, crust/base-Text, radius 10, Hover
     nur Farbe (brightness), kein Lift. */
  .primary {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--accent);
    color: var(--accent-contrast);
    border: none;
    border-radius: var(--r-md);
    padding: 0.55rem 1.2rem;
    font: inherit;
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
    transition: filter var(--dur-fast) var(--ease-out);
  }
  .primary:not(:disabled):hover { filter: brightness(1.12); }
  .primary:not(:disabled):active { filter: brightness(0.95); }
  .primary:disabled { opacity: 0.7; cursor: default; }
  .spinner {
    width: 0.85em;
    height: 0.85em;
    border-radius: 50%;
    border: 2px solid currentColor;
    border-right-color: transparent;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  /* Chip-Rezept für die fertige Kurzlink-Anzeige: surface0, radius 8. */
  .short {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    color: var(--text);
    background: var(--surface0);
    border: 0;
    border-radius: var(--r-xs);
    padding: 0.35rem 0.9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }
  /* Sekundär-Button-Rezept: surface0, Hover surface1. */
  .ghost {
    background: var(--surface0);
    border: 0;
    border-radius: var(--r-md);
    color: var(--text);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 0.35rem 0.85rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out),
                color var(--dur-fast) var(--ease-out);
  }
  .ghost:hover {
    background: var(--surface1);
    color: var(--accent);
  }
  .error { color: var(--error); font-size: 0.88rem; }

  @media (prefers-reduced-motion: reduce) {
    .spinner { animation-duration: 1.8s; }
  }
</style>
