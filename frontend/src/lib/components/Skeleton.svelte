<script lang="ts">
  // Layout placeholder shown while a conversion is in flight.
</script>

<div class="card" aria-busy="true" aria-label="Lädt …">
  <div class="cover shimmer"></div>
  <div class="meta">
    <div class="line shimmer w-60"></div>
    <div class="line shimmer w-40"></div>
    <div class="line shimmer w-90"></div>
    <div class="line shimmer w-90"></div>
    <div class="line shimmer w-90"></div>
  </div>
</div>

<style>
  /* Gleiches Fenster-Primitiv wie ResultCard, damit der Skeleton nicht
     "poppt", wenn er durch das echte Ergebnis ersetzt wird. */
  .card {
    display: flex;
    gap: 1.25rem;
    padding: 1.25rem;
    background: var(--base);
    border-radius: var(--r-xl);
    box-shadow: var(--shadow-card);
  }
  .cover {
    width: 138px;
    height: 138px;
    border-radius: var(--r-md);
    flex-shrink: 0;
  }
  .meta {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    flex: 1;
    padding-top: 0.4rem;
  }
  .line {
    height: 0.85rem;
    border-radius: var(--r-xs);
  }
  .w-40 { width: 40%; }
  .w-60 { width: 60%; }
  .w-90 { width: 90%; }

  /* Shimmer wandert von surface0 zu surface1 — kein Blur, keine
     Akzentfarbe im Chrome. */
  .shimmer {
    background:
      linear-gradient(
        100deg,
        var(--surface0) 0%,
        var(--surface0) 40%,
        var(--surface1) 50%,
        var(--surface0) 60%,
        var(--surface0) 100%
      );
    background-size: 200% 100%;
    animation: shimmer 1.6s ease-in-out infinite;
  }

  @keyframes shimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  @media (max-width: 639px) {
    .card { flex-direction: column; align-items: center; padding: 1.1rem; }
    .cover { width: 100%; max-width: 220px; height: auto; aspect-ratio: 1 / 1; }
    .meta { width: 100%; }
  }

  @media (prefers-reduced-motion: reduce) {
    .shimmer { animation: none; }
  }
</style>
