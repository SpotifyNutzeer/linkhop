<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { TargetResult } from '$lib/api/types';
  import { createCopyFeedback } from '$lib/stores/copyFeedback';

  interface Props {
    serviceId: string;
    displayName: string;
    result: TargetResult;
    isSource?: boolean;
  }

  let {
    serviceId,
    displayName,
    result,
    isSource = false
  }: Props = $props();

  const feedback = createCopyFeedback();
  const { copied, copyFailed } = feedback;

  async function copy() {
    if (!linkUrl) return;
    await feedback.copy(linkUrl);
  }

  onDestroy(() => feedback.destroy());

  let linkUrl =
    $derived((result.status === 'ok' || result.status === 'ok_low') ? result.url ?? null : null);
</script>

<div class="row" class:source={isSource} data-service-id={serviceId}>
  <div class="name">
    <span class="service-name">{displayName}</span>
    {#if isSource}
      <span class="badge source-badge">quelle</span>
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
        onclick={copy}
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
  /* Verschachtelte Tile im Tabellen-Rezept: surface0 in Ruhe, surface1
     bei Hover (die nächste Stufe der Palette-Leiter) — kein Border, kein
     Blur, kein diagonaler Gradient-Tint. */
  .row {
    --brand: var(--overlay0);
    position: relative;
    display: flex;
    gap: 0.75rem;
    align-items: center;
    padding: 0.55rem 0.85rem 0.55rem 1.05rem;
    background: var(--surface0);
    border-radius: var(--r-md);
    overflow: hidden;
    transition: background var(--dur-fast) var(--ease-out);
  }
  /* Brand-Strip links — flach, opak, dient allein der Diensterkennung
     (Content, nicht Chrome). */
  .row::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: var(--brand);
  }
  .row:hover {
    background: var(--surface1);
  }

  /* Marken-Farben pro Dienst — bleiben als Content-Identität erhalten. */
  .row[data-service-id='spotify'] { --brand: #1ed760; }
  .row[data-service-id='deezer']  { --brand: #a238ff; }
  .row[data-service-id='tidal']   { --brand: #25d1da; }
  .row[data-service-id='youtube_music'] { --brand: #ff0000; }
  .name {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    min-width: 6.5rem;
  }
  .service-name {
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.005em;
  }
  .badge {
    font-size: 0.68rem;
    padding: 0.1rem 0.5rem;
    border-radius: var(--r-xs);
    font-weight: 600;
    text-transform: lowercase;
    background: var(--surface1);
  }
  .source-badge {
    color: var(--accent);
  }
  .warn-badge {
    color: var(--warning);
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
    background: var(--surface1);
    border: 0;
    border-radius: var(--r-md);
    color: var(--text);
    font: inherit;
    font-size: 0.78rem;
    font-weight: 500;
    padding: 0.25rem 0.75rem;
    cursor: pointer;
    transition: color var(--dur-fast) var(--ease-out);
  }
  .copy:hover {
    color: var(--accent);
  }
  .muted { color: var(--text-dim); font-style: italic; font-size: 0.88rem; }
  .error { color: var(--error); font-size: 0.88rem; }

  @media (max-width: 520px) {
    .row { flex-direction: column; align-items: flex-start; gap: 0.35rem; }
    .body { width: 100%; }
  }
</style>
