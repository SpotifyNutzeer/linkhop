<script lang="ts">
  import { onDestroy } from 'svelte';
  import { ApiError, type ApiErrorCode } from '$lib/api/types';
  import { createCopyFeedback } from '$lib/stores/copyFeedback';

  interface Props {
    error: ApiError;
  }

  let { error }: Props = $props();

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
    <span class="pulse" aria-hidden="true"></span>
    <h3>{messages[error.code]}</h3>
  </div>
  {#if error.status === 400 && error.message}
    <p class="detail">{error.message}</p>
  {/if}
  <button type="button" class="debug" onclick={copyDebug}>
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
  /* Freie Card wie ResultCard (base, radius 16, Schatten) — kein
     transluzenter Rot-Tint als Hintergrund. Kritikalität kommt allein
     über den linken Akzent-Strip und die rote Überschrift. */
  .panel {
    position: relative;
    padding: 1.1rem 1.25rem 1.1rem 1.5rem;
    background: var(--base);
    border-radius: var(--r-lg);
    box-shadow: var(--shadow-card);
    overflow: hidden;
    animation: card-in var(--dur) var(--ease-spring);
  }
  .panel::before {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: 3px;
    background: var(--error);
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
    animation: pulse 1.6s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.4; }
  }
  h3 {
    margin: 0;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: -0.02em;
    color: var(--error);
  }
  .detail {
    margin: 0 0 0.85rem 0;
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.82rem;
  }
  .debug {
    background: var(--surface0);
    border: 0;
    color: var(--text);
    border-radius: var(--r-md);
    padding: 0.35rem 0.85rem;
    font: inherit;
    font-size: 0.82rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  .debug:hover {
    background: var(--surface1);
  }

  @media (prefers-reduced-motion: reduce) {
    .pulse { animation: none; }
  }
</style>
