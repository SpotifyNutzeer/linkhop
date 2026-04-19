<script lang="ts">
  import { onDestroy } from 'svelte';
  import { ApiError, type ApiErrorCode } from '$lib/api/types';
  import { createCopyFeedback } from '$lib/stores/copyFeedback';

  export let error: ApiError;

  const messages: Record<ApiErrorCode, string> = {
    invalid_url: 'Ungültiger Link.',
    unsupported_service: 'Dieser Dienst wird nicht unterstützt.',
    not_found: 'Kurzlink nicht gefunden.',
    rate_limited: "Zu viele Anfragen — versuch's in einer Minute erneut.",
    server_error: "Server-Fehler. Versuch's gleich nochmal.",
    offline: 'Keine Verbindung zum Server.'
  };

  const feedback = createCopyFeedback();
  const { copied, copyFailed } = feedback;

  async function copyDebug() {
    const ts = new Date().toISOString();
    const text =
      `${error.code}: ${error.message}\n` +
      `URL: ${error.sourceUrl ?? '-'}\n` +
      `Zeit: ${ts}`;
    await feedback.copy(text);
  }

  onDestroy(() => feedback.destroy());
</script>

<section class="panel" role="alert">
  <div class="head">
    <span class="pulse" aria-hidden="true" />
    <h3>{messages[error.code]}</h3>
  </div>
  {#if error.status === 400 && error.message}
    <p class="detail">{error.message}</p>
  {/if}
  <button type="button" class="debug" on:click={copyDebug}>
    {#if $copyFailed}
      Kopieren fehlgeschlagen
    {:else if $copied}
      Kopiert
    {:else}
      Debug-Info kopieren
    {/if}
  </button>
</section>

<style>
  .panel {
    padding: 1.1rem 1.25rem;
    background: var(--error-soft);
    border: 1px solid color-mix(in srgb, var(--error) 55%, transparent);
    border-radius: var(--r-lg);
    backdrop-filter: blur(24px) saturate(170%);
    -webkit-backdrop-filter: blur(24px) saturate(170%);
    box-shadow: var(--glass-shadow);
    animation: card-in var(--dur-slow) var(--ease-out);
  }
  @keyframes card-in {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .head {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin-bottom: 0.4rem;
  }
  .pulse {
    display: inline-block;
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: var(--error);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--error) 60%, transparent);
    animation: pulse 1.6s ease-in-out infinite;
  }
  @keyframes pulse {
    0%   { box-shadow: 0 0 0 0 color-mix(in srgb, var(--error) 45%, transparent); }
    70%  { box-shadow: 0 0 0 8px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }
  h3 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.2rem;
    color: var(--error);
  }
  .detail {
    margin: 0 0 0.85rem 0;
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.82rem;
  }
  .debug {
    background: var(--glass-bg-strong);
    border: 1px solid var(--glass-border);
    color: var(--text);
    border-radius: var(--r-pill);
    padding: 0.35rem 0.85rem;
    font: inherit;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all var(--dur-fast) var(--ease-out);
  }
  .debug:hover {
    border-color: color-mix(in srgb, var(--error) 60%, transparent);
    color: var(--error);
  }

  @media (prefers-reduced-motion: reduce) {
    .pulse { animation: none; }
  }
</style>
