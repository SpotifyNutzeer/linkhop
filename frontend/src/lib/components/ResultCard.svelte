<script lang="ts">
  import type { ConvertResponse } from '$lib/api/types';
  import ServiceList from './ServiceList.svelte';

  export let result: ConvertResponse;
</script>

<article class="card">
  <div class="stage">
    {#if result.source.artwork}
      <img
        class="cover"
        src={result.source.artwork}
        alt={`Cover: ${result.source.title}`}
        loading="lazy"
      />
      <img
        class="bleed"
        src={result.source.artwork}
        alt=""
        aria-hidden="true"
        loading="lazy"
      />
    {:else}
      <div class="cover placeholder" aria-hidden="true" />
    {/if}
  </div>

  <div class="meta">
    <h2 class="title">{result.source.title}</h2>
    {#if result.source.artists.length}
      <p class="artists">{result.source.artists.join(', ')}</p>
    {/if}

    <ServiceList
      sourceService={result.source.service}
      sourceUrl={result.source.url}
      targets={result.targets ?? {}}
    />

    <slot name="share" />
  </div>
</article>

<style>
  .card {
    position: relative;
    display: flex;
    gap: 1.25rem;
    padding: 1.25rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-xl);
    backdrop-filter: blur(32px) saturate(180%);
    -webkit-backdrop-filter: blur(32px) saturate(180%);
    box-shadow: var(--glass-shadow);
    overflow: hidden;
    animation: card-in var(--dur-slow) var(--ease-out);
  }
  @keyframes card-in {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .stage {
    position: relative;
    flex-shrink: 0;
    width: 138px;
    height: 138px;
  }
  .cover {
    width: 100%;
    height: 100%;
    border-radius: var(--r-md);
    object-fit: cover;
    background: var(--glass-bg-strong);
    box-shadow:
      0 1px 0 0 rgba(255, 255, 255, 0.3) inset,
      0 10px 24px -10px rgba(0, 0, 0, 0.5);
  }
  .bleed {
    position: absolute;
    inset: -18px;
    z-index: -1;
    width: calc(100% + 36px);
    height: calc(100% + 36px);
    object-fit: cover;
    filter: blur(22px) saturate(160%);
    opacity: 0.55;
    pointer-events: none;
  }
  .placeholder {
    background:
      linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.02));
  }
  .meta {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    flex: 1;
    min-width: 0;
  }
  .title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.6rem;
    line-height: 1.1;
    letter-spacing: -0.01em;
    color: var(--text);
    overflow-wrap: anywhere;
  }
  .artists {
    margin: 0 0 0.35rem;
    color: var(--text-muted);
    font-size: 0.95rem;
  }

  @media (max-width: 639px) {
    .card { flex-direction: column; align-items: center; text-align: center; padding: 1.1rem; }
    .stage { width: 100%; max-width: 220px; height: auto; aspect-ratio: 1 / 1; }
    .meta { width: 100%; text-align: left; }
  }
</style>
