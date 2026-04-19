<script lang="ts">
  import { ApiError, type ApiErrorCode } from '$lib/api/types';

  export let error: ApiError;

  const messages: Record<ApiErrorCode, string> = {
    invalid_url: 'Ungültiger Link.',
    unsupported_service: 'Dieser Dienst wird nicht unterstützt.',
    not_found: 'Kurzlink nicht gefunden.',
    rate_limited: "Zu viele Anfragen — versuch's in einer Minute erneut.",
    server_error: "Server-Fehler. Versuch's gleich nochmal.",
    offline: 'Keine Verbindung zum Server.'
  };

  let copied = false;

  async function copyDebug() {
    const ts = new Date().toISOString();
    const text =
      `${error.code}: ${error.message}\n` +
      `URL: ${error.sourceUrl ?? '-'}\n` +
      `Zeit: ${ts}`;
    await navigator.clipboard.writeText(text);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }
</script>

<section class="panel" role="alert">
  <h3>{messages[error.code]}</h3>
  {#if error.status === 400 && error.message && error.message !== messages[error.code]}
    <p class="detail">{error.message}</p>
  {/if}
  <button type="button" class="debug" on:click={copyDebug}>
    {copied ? 'Kopiert ✓' : 'Debug-Info kopieren'}
  </button>
</section>

<style>
  .panel {
    padding: 1rem;
    border: 1px solid var(--error);
    border-radius: 8px;
    background: color-mix(in srgb, var(--error) 12%, var(--bg));
  }
  h3 {
    margin: 0 0 0.5rem 0;
    color: var(--error);
  }
  .detail {
    margin: 0 0 0.75rem 0;
    color: var(--text-muted);
  }
  .debug {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 4px;
    padding: 0.3rem 0.6rem;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .debug:hover {
    background: var(--bg-surface);
  }
</style>
