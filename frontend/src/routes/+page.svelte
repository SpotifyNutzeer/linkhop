<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import InputBar from '$lib/components/InputBar.svelte';
  import HistoryDropdown from '$lib/components/HistoryDropdown.svelte';
  import ResultCard from '$lib/components/ResultCard.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import ErrorPanel from '$lib/components/ErrorPanel.svelte';
  import ShareButton from '$lib/components/ShareButton.svelte';
  import { convert } from '$lib/api/client';
  import { ApiError } from '$lib/api/types';
  import { addHistory } from '$lib/stores/history';
  import type { ConvertResponse } from '$lib/api/types';

  let inputValue = $state('');
  let dropdownOpen = $state(false);
  let loading = $state(false);
  let result: ConvertResponse | null = $state(null);
  let error: ApiError | null = $state(null);
  let currentController: AbortController | null = null;

  async function runConvert(url: string) {
    currentController?.abort();
    const ctrl = new AbortController();
    currentController = ctrl;
    loading = true;
    error = null;
    result = null;
    inputValue = url;
    try {
      const res = await convert(url, { signal: ctrl.signal });
      if (ctrl.signal.aborted) return;
      result = res;
      addHistory({
        sourceUrl: url,
        title: res.source.title,
        artists: res.source.artists,
        coverUrl: res.source.artwork || null,
        timestamp: Date.now()
      });
    } catch (e) {
      if (ctrl.signal.aborted || (e as DOMException).name === 'AbortError') return;
      error = e instanceof ApiError ? e : new ApiError('server_error', 0, String(e), url);
    } finally {
      if (currentController === ctrl) {
        loading = false;
        currentController = null;
      }
    }
  }

  function onWrapFocusOut(event: FocusEvent) {
    // Close the dropdown only when focus leaves the wrap entirely. Moving
    // focus between the input and a listbox option (or vice versa) stays
    // inside currentTarget, so the dropdown remains open while the user
    // navigates with the keyboard or is about to click a history entry.
    const next = event.relatedTarget as Node | null;
    const wrap = event.currentTarget as HTMLElement;
    if (!next || !wrap.contains(next)) {
      dropdownOpen = false;
    }
  }

  onMount(() => {
    const urlParam = $page.url.searchParams.get('url');
    if (urlParam) runConvert(urlParam);
  });
</script>

<div class="home">
  <div class="input-wrap" onfocusout={onWrapFocusOut}>
    <InputBar
      bind:value={inputValue}
      disabled={loading}
      onsubmit={(detail) => runConvert(detail.url)}
      onfocus={() => (dropdownOpen = true)}
    />
    <HistoryDropdown
      open={dropdownOpen}
      onselect={(detail) => {
        dropdownOpen = false;
        runConvert(detail.url);
      }}
      onclose={() => (dropdownOpen = false)}
    />
  </div>

  {#if loading}
    <Skeleton />
  {:else if error}
    {#key error}
      <ErrorPanel {error} />
    {/key}
  {:else if result}
    <ResultCard {result}>
      {#snippet share(res)}
        <ShareButton sourceUrl={res.source.url} />
      {/snippet}
    </ResultCard>
  {/if}
</div>

<style>
  .home {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  .input-wrap {
    position: relative;
  }
</style>
