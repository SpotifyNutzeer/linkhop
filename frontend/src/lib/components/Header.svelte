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
  .hdr {
    position: sticky;
    top: 1rem;
    z-index: 10;
    padding: 0 clamp(1rem, 4vw, 2rem);
    margin: 1rem auto 0;
    max-width: 780px;
  }
  .shell {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.55rem 0.65rem 0.55rem 1rem;
    border-radius: var(--r-pill);
    background: var(--glass-bg-strong);
    border: 1px solid var(--glass-border);
    backdrop-filter: blur(22px) saturate(180%);
    -webkit-backdrop-filter: blur(22px) saturate(180%);
    box-shadow: var(--glass-shadow);
  }
  .brand {
    display: inline-flex;
    align-items: baseline;
    gap: 0.55rem;
    color: var(--text);
    font-family: var(--font-display);
    font-size: 1.45rem;
    line-height: 1;
    letter-spacing: -0.01em;
  }
  .mark {
    display: inline-block;
    font-size: 1.15rem;
    color: var(--accent);
    transform: translateY(1px);
    filter: drop-shadow(0 0 8px var(--accent-soft));
  }
  .word em {
    font-style: italic;
    color: var(--accent);
  }
</style>
