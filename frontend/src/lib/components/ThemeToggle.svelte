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
  onclick={cycleTheme}
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
  /* Sekundär-Button-Rezept als Icon-Kreis: surface0, kein Border, Hover
     surface1. Farbe/Opacity 200ms, die Icon-Drehung bleibt als Jelly-
     Mikrointeraktion (Position/Größe, 350ms Überschwingen). */
  .theme-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.4rem;
    height: 2.4rem;
    padding: 0;
    background: var(--surface0);
    border: 0;
    border-radius: 50%;
    color: var(--text);
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out),
                color var(--dur-fast) var(--ease-out);
  }
  .theme-toggle:hover {
    background: var(--surface1);
    color: var(--accent);
  }
  .theme-toggle:hover .icon { transform: rotate(-8deg); }
  .theme-toggle:active { transform: scale(0.95); }
  .icon {
    display: inline-flex;
    transition: transform var(--dur) var(--ease-spring);
  }

  @media (prefers-reduced-motion: reduce) {
    .theme-toggle:hover .icon { transform: none; }
  }
</style>
