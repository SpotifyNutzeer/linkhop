<script lang="ts">
  import { themePref, cycleTheme, type Pref } from '$lib/stores/theme';

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
  <span class="icon" aria-hidden="true">
    {#if $themePref === 'auto'}
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none"
           stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="8" />
        <path d="M12 4 A 8 8 0 0 1 12 20 Z" fill="currentColor" stroke="none" />
      </svg>
    {:else if $themePref === 'dark'}
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none"
           stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
      </svg>
    {:else}
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none"
           stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      </svg>
    {/if}
  </span>
</button>

<style>
  .theme-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.4rem;
    height: 2.4rem;
    padding: 0;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 50%;
    color: var(--text);
    cursor: pointer;
    backdrop-filter: blur(14px) saturate(170%);
    -webkit-backdrop-filter: blur(14px) saturate(170%);
    transition: all var(--dur-fast) var(--ease-out);
  }
  .theme-toggle:hover {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 55%, transparent);
    transform: rotate(-8deg);
  }
  .theme-toggle:active { transform: scale(0.95); }
  .icon {
    display: inline-flex;
    transition: transform var(--dur) var(--ease-spring);
  }

  @media (prefers-reduced-motion: reduce) {
    .theme-toggle:hover { transform: none; }
  }
</style>
