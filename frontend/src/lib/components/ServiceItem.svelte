<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { TargetResult } from '$lib/api/types';
  import { createCopyFeedback } from '$lib/stores/copyFeedback';

  export let serviceId: string;
  export let displayName: string;
  export let result: TargetResult;
  export let isSource = false;

  const feedback = createCopyFeedback();
  const { copied, copyFailed } = feedback;

  async function copy() {
    if (!linkUrl) return;
    await feedback.copy(linkUrl);
  }

  onDestroy(() => feedback.destroy());

  $: linkUrl =
    (result.status === 'ok' || result.status === 'ok_low') ? result.url ?? null : null;
</script>

<div class="row" class:source={isSource} data-service-id={serviceId}>
  <div class="name">
    <span class="service-name">{displayName}</span>
    {#if isSource}
      <span class="badge source-badge">Quelle</span>
    {/if}
    {#if result.status === 'ok_low'}
      <span class="badge warn-badge" title="Ungenaue Übereinstimmung">~match</span>
    {/if}
  </div>

  <div class="body">
    {#if linkUrl}
      <a class="link" href={linkUrl} target="_blank" rel="noopener noreferrer">
        {linkUrl}
      </a>
      <button
        type="button"
        class="copy"
        aria-label="Link kopieren"
        on:click={copy}
      >
        {#if $copyFailed}
          Fehlgeschlagen
        {:else if $copied}
          Kopiert
        {:else}
          Kopieren
        {/if}
      </button>
    {:else if result.status === 'not_found'}
      <span class="muted">nicht gefunden</span>
    {:else if result.status === 'error'}
      <span class="error">Fehler{result.message ? `: ${result.message}` : ''}</span>
    {/if}
  </div>
</div>

<style>
  .row {
    --brand: var(--text-muted);
    position: relative;
    display: flex;
    gap: 0.75rem;
    align-items: center;
    padding: 0.55rem 0.85rem 0.55rem 1.05rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-md);
    backdrop-filter: blur(18px) saturate(170%);
    -webkit-backdrop-filter: blur(18px) saturate(170%);
    overflow: hidden;
    transition: border-color var(--dur-fast) var(--ease-out),
                background var(--dur-fast) var(--ease-out);
  }
  /* Brand-Strip links + diagonal angedeuteter Farb-Tint im Hintergrund. */
  .row::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: var(--brand);
    box-shadow: 0 0 14px 0 color-mix(in srgb, var(--brand) 55%, transparent);
    opacity: 0.85;
  }
  .row::after {
    content: '';
    position: absolute;
    inset: 0;
    background:
      linear-gradient(
        115deg,
        color-mix(in srgb, var(--brand) 14%, transparent) 0%,
        transparent 55%
      );
    pointer-events: none;
    transition: opacity var(--dur-fast) var(--ease-out);
    opacity: 0.6;
  }
  .row:hover {
    background: var(--glass-bg-strong);
    border-color: color-mix(in srgb, var(--brand) 45%, var(--glass-border));
  }
  .row:hover::after { opacity: 1; }
  .row.source {
    border-color: color-mix(in srgb, var(--accent) 60%, transparent);
  }
  .row.source::after {
    background:
      linear-gradient(
        115deg,
        color-mix(in srgb, var(--brand) 18%, transparent) 0%,
        var(--accent-soft) 55%,
        transparent 100%
      );
    opacity: 1;
  }

  /* Brand-Farben pro Dienst — bewusst gedämpft, damit sie auf Light & Dark
     lesbar bleiben und dem Glass-Look nicht das Wasser abgraben. */
  .row[data-service-id='spotify'] { --brand: #1ed760; }
  .row[data-service-id='deezer']  { --brand: #a238ff; }
  .row[data-service-id='tidal']   { --brand: #25d1da; }
  .name {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    min-width: 6.5rem;
  }
  .service-name {
    font-weight: 600;
    color: color-mix(in srgb, var(--brand) 80%, var(--text));
    letter-spacing: 0.005em;
  }
  /* name + body liegen über dem ::after-Tint */
  .name, .body { position: relative; z-index: 1; }
  .badge {
    font-size: 0.65rem;
    padding: 0.1rem 0.5rem;
    border-radius: var(--r-pill);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .source-badge {
    color: var(--accent);
    background: var(--accent-soft);
    border: 1px solid color-mix(in srgb, var(--accent) 50%, transparent);
  }
  .warn-badge {
    color: var(--warning);
    background: color-mix(in srgb, var(--warning) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--warning) 50%, transparent);
  }
  .body {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex: 1;
    min-width: 0;
  }
  .link {
    font-family: var(--font-mono);
    font-size: 0.82rem;
    color: var(--text-muted);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
    transition: color var(--dur-fast) var(--ease-out);
  }
  .link:hover { color: var(--accent); }
  .copy {
    background: var(--glass-bg-strong);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-pill);
    color: var(--text);
    font: inherit;
    font-size: 0.78rem;
    font-weight: 500;
    padding: 0.25rem 0.75rem;
    cursor: pointer;
    transition: all var(--dur-fast) var(--ease-out);
  }
  .copy:hover {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 60%, transparent);
  }
  .muted { color: var(--text-dim); font-style: italic; font-size: 0.88rem; }
  .error { color: var(--error); font-size: 0.88rem; }

  @media (max-width: 520px) {
    .row { flex-direction: column; align-items: flex-start; gap: 0.35rem; }
    .body { width: 100%; }
  }
</style>
