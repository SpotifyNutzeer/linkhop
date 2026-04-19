<script lang="ts">
  // Layout placeholder shown while a conversion is in flight.
</script>

<div class="card" aria-busy="true" aria-label="Lädt …">
  <div class="cover shimmer" />
  <div class="meta">
    <div class="line shimmer w-60" />
    <div class="line shimmer w-40" />
    <div class="line shimmer w-90" />
    <div class="line shimmer w-90" />
    <div class="line shimmer w-90" />
  </div>
</div>

<style>
  .card {
    display: flex;
    gap: 1.25rem;
    padding: 1.25rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--r-xl);
    backdrop-filter: blur(32px) saturate(180%);
    -webkit-backdrop-filter: blur(32px) saturate(180%);
    box-shadow: var(--glass-shadow);
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

  .shimmer {
    background:
      linear-gradient(
        100deg,
        var(--glass-bg-strong) 0%,
        var(--glass-bg-strong) 40%,
        var(--accent-soft) 50%,
        var(--glass-bg-strong) 60%,
        var(--glass-bg-strong) 100%
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
