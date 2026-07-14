<script lang="ts">
  import '@fontsource-variable/jetbrains-mono';
  import '@fontsource-variable/jetbrains-mono/wght-italic.css';
  import '$lib/theme/tokens.css';
  import Header from '$lib/components/Header.svelte';
  import { onMount } from 'svelte';
  import { services as servicesStore } from '$lib/stores/services';
  import { services as fetchServices } from '$lib/api/client';
  interface Props {
    children?: import('svelte').Snippet;
  }

  let { children }: Props = $props();

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
  {@render children?.()}
</main>

<!-- Zen-Frame wie Frame.qml / paul.wtf's Layout.astro: Mantle-Rahmenstreifen
     (als Border) plus vier konkave Viewport-Ecken (Radial-Gradients). Oben
     endet der Viewport an der Bar (--viewport-top = --bar-h), die die
     Rahmenkante ersetzt. Als letztes Element im Root-Layout, damit es über
     allem liegt (Bezel-Metapher); pointer-events: none macht es unsichtbar
     für Interaktion. Gilt auf jeder Route, da Header hier global rendert. -->
<div class="zen-frame" aria-hidden="true"><i></i><i></i><i></i><i></i></div>

<style>
  main {
    max-width: 720px;
    margin: 0 auto;
    padding: clamp(1.5rem, 4vw, 3rem) clamp(1rem, 4vw, 2rem) 4rem;
  }

  /* NIEMALS box-shadow: 0 0 0 100vmax statt border verwenden — bricht die
     Tile-Rasterization in Chromium bei Full-Page-Rendering (auf paul.wtf
     verifiziert). Nur das Border-Rezept unten. */
  .zen-frame {
    position: fixed;
    inset: 0;
    border: solid var(--mantle);
    border-width: var(--viewport-top) var(--frame) var(--frame);
    pointer-events: none;
    z-index: 60;
  }
  .zen-frame i {
    position: absolute;
    width: var(--viewport-r);
    height: var(--viewport-r);
  }
  .zen-frame i:nth-child(1) {
    top: 0;
    left: 0;
    background: radial-gradient(
      circle at 100% 100%,
      transparent calc(var(--viewport-r) - 0.5px),
      var(--mantle) var(--viewport-r)
    );
  }
  .zen-frame i:nth-child(2) {
    top: 0;
    right: 0;
    background: radial-gradient(
      circle at 0% 100%,
      transparent calc(var(--viewport-r) - 0.5px),
      var(--mantle) var(--viewport-r)
    );
  }
  .zen-frame i:nth-child(3) {
    bottom: 0;
    left: 0;
    background: radial-gradient(
      circle at 100% 0%,
      transparent calc(var(--viewport-r) - 0.5px),
      var(--mantle) var(--viewport-r)
    );
  }
  .zen-frame i:nth-child(4) {
    bottom: 0;
    right: 0;
    background: radial-gradient(
      circle at 0% 0%,
      transparent calc(var(--viewport-r) - 0.5px),
      var(--mantle) var(--viewport-r)
    );
  }
</style>
