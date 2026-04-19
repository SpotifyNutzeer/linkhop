<script lang="ts">
  import { onDestroy } from 'svelte';
  import { convert } from '$lib/api/client';
  import { ApiError } from '$lib/api/types';
  import { createCopyFeedback } from '$lib/stores/copyFeedback';

  export let sourceUrl: string;

  type State = 'idle' | 'loading' | 'done' | 'error';

  let state: State = 'idle';
  let shortUrl = '';
  let shareError: ApiError | null = null;
  let currentController: AbortController | null = null;

  const feedback = createCopyFeedback();
  const { copied, copyFailed } = feedback;

  async function share() {
    currentController?.abort();
    const ctrl = new AbortController();
    currentController = ctrl;
    state = 'loading';
    shareError = null;
    try {
      const res = await convert(sourceUrl, { share: true, signal: ctrl.signal });
      if (ctrl.signal.aborted) return;
      const info = res.share;
      if (!info?.id) {
        shareError = new ApiError('server_error', 0, 'Antwort ohne Share-ID', sourceUrl);
        state = 'error';
        return;
      }
      shortUrl = info.url ?? `${window.location.origin}/c/${info.id}`;
      state = 'done';
    } catch (e) {
      if (ctrl.signal.aborted || (e as DOMException).name === 'AbortError') return;
      shareError = e instanceof ApiError ? e : new ApiError('server_error', 0, String(e), sourceUrl);
      state = 'error';
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
  {#if state === 'idle'}
    <button type="button" class="primary" on:click={share}>Teilen</button>
  {:else if state === 'loading'}
    <button type="button" class="primary" disabled>
      <span class="spinner" aria-hidden="true" />
      Erzeuge Link …
    </button>
  {:else if state === 'done'}
    <code class="short">{shortUrl}</code>
    <button type="button" class="ghost" aria-label="Kurzlink kopieren" on:click={copy}>
      {#if $copyFailed}
        Fehlgeschlagen
      {:else if $copied}
        Kopiert
      {:else}
        Kopieren
      {/if}
    </button>
  {:else if state === 'error'}
    <span class="error">Fehler beim Erzeugen des Links</span>
    <button type="button" class="ghost" on:click={share}>Nochmal</button>
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
  .primary {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--accent);
    color: var(--accent-contrast);
    border: none;
    border-radius: var(--r-pill);
    padding: 0.55rem 1.2rem;
    font: inherit;
    font-weight: 600;
    font-size: 0.9rem;
    cursor: pointer;
    box-shadow:
      0 1px 0 0 rgba(255, 255, 255, 0.35) inset,
      0 -1px 0 0 rgba(0, 0, 0, 0.18) inset,
      0 8px 20px -10px rgba(0, 0, 0, 0.45);
    transition: transform var(--dur-fast) var(--ease-spring),
                filter var(--dur-fast) var(--ease-out);
  }
  .primary:not(:disabled):hover { filter: brightness(1.06); transform: translateY(-1px); }
  .primary:not(:disabled):active { transform: translateY(0); filter: brightness(0.95); }
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
  .short {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    color: var(--text);
    background: var(--glass-bg-strong);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-pill);
    padding: 0.35rem 0.9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
    backdrop-filter: blur(14px) saturate(170%);
    -webkit-backdrop-filter: blur(14px) saturate(170%);
  }
  .ghost {
    background: var(--glass-bg-strong);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-pill);
    color: var(--text);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 0.35rem 0.85rem;
    cursor: pointer;
    transition: all var(--dur-fast) var(--ease-out);
  }
  .ghost:hover {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 60%, transparent);
  }
  .error { color: var(--error); font-size: 0.88rem; }

  @media (prefers-reduced-motion: reduce) {
    .spinner { animation-duration: 1.8s; }
  }
</style>
