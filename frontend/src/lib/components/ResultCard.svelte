<script lang="ts">
  import type { ConvertResponse } from '$lib/api/types';
  import ServiceList from './ServiceList.svelte';

  interface Props {
    result: ConvertResponse;
    share?: import('svelte').Snippet<[ConvertResponse]>;
  }

  let { result, share }: Props = $props();
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
    {:else}
      <div class="cover placeholder" aria-hidden="true"></div>
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

    {@render share?.(result)}
  </div>
</article>

<style>
  /* Fenster-Primitiv: opak (base), borderlos, Schatten nur hier — die
     ResultCard ist die einzige freie Card auf der Seite. Der blaue
     Blur-„Bleed" hinter dem Cover war Liquid-Glass-Vokabular und
     entfällt ersatzlos. */
  .card {
    position: relative;
    display: flex;
    gap: 1.25rem;
    padding: 1.25rem;
    background: var(--base);
    border-radius: var(--r-xl);
    box-shadow: var(--shadow-card);
    overflow: hidden;
    animation: card-in var(--dur) var(--ease-spring);
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
    background: var(--surface0);
  }
  .placeholder {
    background: var(--surface0);
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
    font-weight: 700;
    font-size: 1.4rem;
    line-height: 1.15;
    letter-spacing: -0.02em;
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
