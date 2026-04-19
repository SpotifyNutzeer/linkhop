<script lang="ts">
  import '$lib/theme/tokens.css';
  import Header from '$lib/components/Header.svelte';
  import { onMount } from 'svelte';
  import { services as servicesStore } from '$lib/stores/services';
  import { services as fetchServices } from '$lib/api/client';

  onMount(async () => {
    try {
      const res = await fetchServices();
      const map = Object.fromEntries(res.services.map((s) => [s.id, s]));
      servicesStore.set(map);
    } catch {
      // Services-Load ist Best-Effort: bei Fehler bleibt die Map leer,
      // ServiceItem fällt auf Service-ID als Display-Name zurück.
    }
  });
</script>

<Header />
<main>
  <slot />
</main>

<style>
  main {
    max-width: 960px;
    margin: 0 auto;
    padding: 1.5rem;
  }
</style>
