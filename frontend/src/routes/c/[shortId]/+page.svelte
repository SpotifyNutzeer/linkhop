<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import ResultCard from '$lib/components/ResultCard.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import ErrorPanel from '$lib/components/ErrorPanel.svelte';
  import { lookup } from '$lib/api/client';
  import { ApiError } from '$lib/api/types';
  import type { ConvertResponse } from '$lib/api/types';

  let loading = true;
  let result: ConvertResponse | null = null;
  let error: ApiError | null = null;

  onMount(async () => {
    // Route matcher /c/[shortId] guarantees a non-empty string here.
    const shortId = $page.params.shortId!;
    try {
      result = await lookup(shortId);
    } catch (e) {
      error = e instanceof ApiError ? e : new ApiError('server_error', 0, String(e));
    } finally {
      loading = false;
    }
  });
</script>

<div class="lookup">
  {#if loading}
    <Skeleton />
  {:else if error}
    {#key error}
      <ErrorPanel {error} />
    {/key}
  {:else if result}
    <ResultCard {result} />
  {/if}
</div>

<style>
  .lookup {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
</style>
