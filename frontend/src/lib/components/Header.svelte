<script lang="ts">
  import ThemeToggle from './ThemeToggle.svelte';
</script>

<header class="hdr">
  <span class="brand">linkhop.</span>
  <ThemeToggle />
</header>

<style>
  .hdr {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border);
  }
  .brand {
    color: var(--accent);
    font-weight: 700;
    font-size: 1.4rem;
    letter-spacing: -0.02em;
  }
</style>
