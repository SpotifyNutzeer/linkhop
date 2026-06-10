<script lang="ts">
  import type { ConvertResponse, TargetResult } from '$lib/api/types';
  import { services } from '$lib/stores/services';
  import ServiceItem from './ServiceItem.svelte';

  interface Props {
    sourceService: string;
    sourceUrl: string;
    targets: ConvertResponse['targets'];
  }

  let { sourceService, sourceUrl, targets }: Props = $props();

  function displayName(id: string): string {
    return $services[id]?.name ?? id;
  }

  let sourceResult = $derived({ status: 'ok', url: sourceUrl } satisfies TargetResult);
  let targetEntries = $derived(Object.entries(targets).filter(([id]) => id !== sourceService));
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
    gap: 0.4rem;
    margin-top: 0.85rem;
  }
</style>
