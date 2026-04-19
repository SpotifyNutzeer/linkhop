<script lang="ts">
  import type { ConvertResponse } from '$lib/api/types';
  import ServiceList from './ServiceList.svelte';

  export let result: ConvertResponse;
</script>

<article class="card">
  {#if result.source.artwork}
    <img
      class="cover"
      src={result.source.artwork}
      alt={`Cover: ${result.source.title}`}
      loading="lazy"
    />
  {:else}
    <div class="cover placeholder" aria-hidden="true" />
  {/if}

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
    display: flex;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-surface);
  }
  .cover {
    width: 130px;
    height: 130px;
    border-radius: 6px;
    object-fit: cover;
    flex-shrink: 0;
    background: var(--border);
  }
  .placeholder {
    display: block;
  }
  .meta {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    flex: 1;
    min-width: 0;
  }
  .title {
    font-size: 1.2rem;
    margin: 0;
    color: var(--text);
  }
  .artists {
    margin: 0;
    color: var(--text-muted);
  }

  @media (max-width: 639px) {
    .card {
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    .cover {
      width: 100%;
      max-width: 220px;
      height: auto;
      aspect-ratio: 1 / 1;
    }
    .meta {
      width: 100%;
      text-align: left;
    }
  }
</style>
