<script lang="ts">
  import ThemeToggle from './ThemeToggle.svelte';
</script>

<header class="hdr">
  <div class="shell">
    <span class="brand">
      <span class="mark" aria-hidden="true">◐</span>
      <span class="word">link<em>hop</em>.</span>
    </span>
    <ThemeToggle />
  </div>
</header>

<style>
  /* Volle Breite, opakes Mantle, borderlos, kein Scroll-Blur — wie
     Bar.qml (zen) / paul.wtf's Nav.astro. Ersetzt die schwebende
     Pill-Shell. */
  .hdr {
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--mantle);
  }
  .shell {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    max-width: 780px;
    margin: 0 auto;
    padding: 0.7rem clamp(1rem, 4vw, 2rem);
  }
  .brand {
    display: inline-flex;
    align-items: baseline;
    gap: 0.5rem;
    color: var(--text);
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.15rem;
    line-height: 1;
    letter-spacing: -0.02em;
  }
  .mark {
    display: inline-block;
    font-size: 1.05rem;
    color: var(--accent);
    transform: translateY(1px);
  }
  .word em {
    font-style: normal;
    color: var(--accent);
  }
</style>
