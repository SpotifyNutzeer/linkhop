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

  let inputValue = '';
  let dropdownOpen = false;
  let loading = false;
  let result: ConvertResponse | null = null;
  let error: ApiError | null = null;
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

  function onInputBlur() {
    // Blur->click race workaround (not a debounce): without the delay, clicking a
    // HistoryDropdown item blurs the input, hides the dropdown, and the click lands
    // on nothing. 150ms lets the click fire before the dropdown detaches.
    setTimeout(() => {
      dropdownOpen = false;
    }, 150);
  }

  onMount(() => {
    const urlParam = $page.url.searchParams.get('url');
    if (urlParam) runConvert(urlParam);
  });
</script>

<div class="home">
  <div class="input-wrap">
    <InputBar
      bind:value={inputValue}
      disabled={loading}
      on:submit={(e) => runConvert(e.detail.url)}
      on:focus={() => (dropdownOpen = true)}
      on:blur={onInputBlur}
    />
    <HistoryDropdown
      open={dropdownOpen}
      on:select={(e) => {
        dropdownOpen = false;
        runConvert(e.detail.url);
      }}
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
      <svelte:fragment slot="share">
        <ShareButton sourceUrl={result.source.url} />
      </svelte:fragment>
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
