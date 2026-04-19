<script lang="ts">
  import type { ConvertResponse, TargetResult } from '$lib/api/types';
  import { services } from '$lib/stores/services';
  import ServiceItem from './ServiceItem.svelte';

  export let sourceService: string;
  export let sourceUrl: string;
  export let targets: ConvertResponse['targets'];

  function displayName(id: string): string {
    return $services[id]?.name ?? id;
  }

  $: sourceResult = { status: 'ok', url: sourceUrl } satisfies TargetResult;
  $: targetEntries = Object.entries(targets).filter(([id]) => id !== sourceService);
</script>

<div class="list">
  <ServiceItem
    serviceId={sourceService}
    displayName={displayName(sourceService)}
    result={sourceResult}
    isSource
  />
  {#each targetEntries as [id, result] (id)}
    <ServiceItem
      serviceId={id}
      displayName={displayName(id)}
      {result}
    />
  {/each}
</div>

<style>
  .list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }
</style>
