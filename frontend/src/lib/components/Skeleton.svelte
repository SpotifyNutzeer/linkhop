<script lang="ts">
  // Layout placeholder shown while a conversion is in flight.
</script>

<div class="card" aria-busy="true" aria-label="Lädt …">
  <div class="cover pulse" />
  <div class="meta">
    <div class="line pulse w-60" />
    <div class="line pulse w-40" />
    <div class="line pulse w-90" />
    <div class="line pulse w-90" />
    <div class="line pulse w-90" />
  </div>
</div>

<style>
  .card {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-surface);
  }
  .cover {
    width: 130px;
    height: 130px;
    border-radius: 6px;
    background: var(--border);
    flex-shrink: 0;
  }
  .meta {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    flex: 1;
  }
  .line {
    height: 0.9rem;
    background: var(--border);
    border-radius: 4px;
  }
  .w-40 { width: 40%; }
  .w-60 { width: 60%; }
  .w-90 { width: 90%; }

  .pulse {
    animation: pulse 1.2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.55; }
    50%      { opacity: 1; }
  }

  @media (max-width: 639px) {
    .card {
      flex-direction: column;
      align-items: center;
    }
    .cover {
      width: 100%;
      max-width: 220px;
      height: auto;
      aspect-ratio: 1 / 1;
    }
    .meta {
      width: 100%;
    }
  }
</style>
