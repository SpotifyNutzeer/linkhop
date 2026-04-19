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
    <span>{displayName}</span>
    {#if isSource}
      <span class="badge source-badge">(Quelle)</span>
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
          Kopieren fehlgeschlagen
        {:else if $copied}
          ✓
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
    display: flex;
    gap: 0.75rem;
    align-items: center;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg-surface);
  }
  .row.source {
    border-color: var(--accent);
  }
  .name {
    display: flex;
    gap: 0.35rem;
    align-items: center;
    min-width: 7rem;
    font-weight: 600;
    color: var(--text);
  }
  .badge {
    font-size: 0.7rem;
    padding: 0.05rem 0.4rem;
    border-radius: 999px;
    font-weight: 500;
  }
  .source-badge {
    color: var(--accent);
    border: 1px solid var(--accent);
  }
  .warn-badge {
    color: var(--warning);
    border: 1px solid var(--warning);
  }
  .body {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex: 1;
    min-width: 0;
  }
  .link {
    color: var(--accent);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }
  .link:hover {
    text-decoration: underline;
  }
  .copy {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    padding: 0.2rem 0.6rem;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .copy:hover {
    border-color: var(--accent);
    color: var(--accent);
  }
  .muted {
    color: var(--text-muted);
    font-style: italic;
  }
  .error {
    color: var(--error);
  }
</style>
