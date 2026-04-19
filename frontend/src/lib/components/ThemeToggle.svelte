<script lang="ts">
  import { themePref, cycleTheme, type Pref } from '$lib/stores/theme';

  const icons: Record<Pref, string> = { auto: '🌓', dark: '🌙', light: '☀️' };
  const labels: Record<Pref, string> = {
    auto: 'Theme: automatisch, zum Wechseln klicken',
    dark: 'Theme: dunkel, zum Wechseln klicken',
    light: 'Theme: hell, zum Wechseln klicken'
  };
</script>

<button
  type="button"
  class="theme-toggle"
  aria-label={labels[$themePref]}
  on:click={cycleTheme}
>
  {icons[$themePref]}
</button>

<style>
  .theme-toggle {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    cursor: pointer;
    font-size: 1.2rem;
    padding: 0.4rem 0.6rem;
  }
  .theme-toggle:hover { background: var(--bg-surface); }
</style>
