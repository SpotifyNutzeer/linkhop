<script lang="ts">
  import { onDestroy } from 'svelte';
  import { convert } from '$lib/api/client';
  import { ApiError } from '$lib/api/types';

  export let sourceUrl: string;

  type State = 'idle' | 'loading' | 'done' | 'error';

  let state: State = 'idle';
  let shortUrl = '';
  let shareError: ApiError | null = null;
  let currentController: AbortController | null = null;

  let copied = false;
  let copyFailed = false;
  let copyTimer: ReturnType<typeof setTimeout> | null = null;

  function scheduleReset() {
    if (copyTimer) clearTimeout(copyTimer);
    copyTimer = setTimeout(() => {
      copied = false;
      copyFailed = false;
      copyTimer = null;
    }, 1500);
  }

  async function share() {
    currentController?.abort();
    const ctrl = new AbortController();
    currentController = ctrl;
    state = 'loading';
    shareError = null;
    try {
      const res = await convert(sourceUrl, { share: true, signal: ctrl.signal });
      if (ctrl.signal.aborted) return;
      const info = (res as { share?: { id: string; url: string } }).share;
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
    try {
      await navigator.clipboard.writeText(shortUrl);
      copied = true;
      copyFailed = false;
      scheduleReset();
    } catch {
      copied = false;
      copyFailed = true;
      scheduleReset();
    }
  }

  onDestroy(() => {
    if (copyTimer) clearTimeout(copyTimer);
    currentController?.abort();
  });
</script>

<div class="share">
  {#if state === 'idle'}
    <button type="button" class="primary" on:click={share}>Teilen</button>
  {:else if state === 'loading'}
    <button type="button" class="primary" disabled>Erzeuge Link …</button>
  {:else if state === 'done'}
    <code class="short">{shortUrl}</code>
    <button type="button" class="copy" aria-label="Kurzlink kopieren" on:click={copy}>
      {#if copyFailed}
        Kopieren fehlgeschlagen
      {:else if copied}
        ✓
      {:else}
        Kopieren
      {/if}
    </button>
  {:else if state === 'error'}
    <span class="error">Fehler beim Erzeugen des Links</span>
    <button type="button" class="retry" on:click={share}>Nochmal</button>
  {/if}
</div>

<style>
  .share {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 0.75rem;
  }
  .primary {
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: 4px;
    padding: 0.35rem 0.8rem;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .primary:disabled {
    opacity: 0.6;
    cursor: default;
  }
  .primary:not(:disabled):hover {
    filter: brightness(1.1);
  }
  .short {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.2rem 0.5rem;
    font-size: 0.85rem;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }
  .copy,
  .retry {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    padding: 0.2rem 0.6rem;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .copy:hover,
  .retry:hover {
    border-color: var(--accent);
    color: var(--accent);
  }
  .error {
    color: var(--error);
    font-size: 0.9rem;
  }
</style>
