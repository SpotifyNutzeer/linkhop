import { writable, type Readable } from 'svelte/store';

export interface CopyFeedback {
  /** `true` for `resetMs` after a successful copy, else `false`. */
  copied: Readable<boolean>;
  /** `true` for `resetMs` after a failed copy, else `false`. */
  copyFailed: Readable<boolean>;
  /**
   * Try to copy `text` to the clipboard. Reflects the outcome via
   * `copied` / `copyFailed`. Never rejects; failures (including a missing
   * `navigator.clipboard`) surface as `copyFailed = true`.
   */
  copy: (text: string) => Promise<void>;
  /** Clear any pending reset timer. Call from `onDestroy`. */
  destroy: () => void;
}

/**
 * State machine for "copy → show ✓ for resetMs, else show failure for resetMs".
 * One instance per component call site.
 */
export function createCopyFeedback(resetMs = 1500): CopyFeedback {
  const copied = writable(false);
  const copyFailed = writable(false);
  let timer: ReturnType<typeof setTimeout> | null = null;

  function clearTimer() {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
  }

  function scheduleReset() {
    clearTimer();
    timer = setTimeout(() => {
      timer = null;
      copied.set(false);
      copyFailed.set(false);
    }, resetMs);
  }

  async function copy(text: string): Promise<void> {
    // Cancel any stale pending reset from a previous call so it can't flip
    // the fresh state back once it fires.
    clearTimer();
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('clipboard unavailable');
      }
      await navigator.clipboard.writeText(text);
      copied.set(true);
      copyFailed.set(false);
    } catch {
      copied.set(false);
      copyFailed.set(true);
    }
    scheduleReset();
  }

  return {
    copied: { subscribe: copied.subscribe },
    copyFailed: { subscribe: copyFailed.subscribe },
    copy,
    destroy: clearTimer
  };
}
