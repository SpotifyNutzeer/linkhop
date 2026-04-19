import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { createCopyFeedback } from './copyFeedback';

function stubClipboard(writeText: (t: string) => Promise<void>) {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText },
    configurable: true,
    writable: true
  });
}

function removeClipboard() {
  Object.defineProperty(navigator, 'clipboard', {
    value: undefined,
    configurable: true,
    writable: true
  });
}

describe('createCopyFeedback', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('starts with copied=false and copyFailed=false', () => {
    const fb = createCopyFeedback();
    expect(get(fb.copied)).toBe(false);
    expect(get(fb.copyFailed)).toBe(false);
  });

  it('flips copied=true after a successful write', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    const fb = createCopyFeedback();
    await fb.copy('hello');
    expect(writeText).toHaveBeenCalledWith('hello');
    expect(get(fb.copied)).toBe(true);
    expect(get(fb.copyFailed)).toBe(false);
  });

  it('resets copied back to false after resetMs', async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    const fb = createCopyFeedback(1500);
    await fb.copy('hello');
    expect(get(fb.copied)).toBe(true);
    vi.advanceTimersByTime(1500);
    expect(get(fb.copied)).toBe(false);
    expect(get(fb.copyFailed)).toBe(false);
  });

  it('flips copyFailed=true when writeText rejects', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'));
    stubClipboard(writeText);
    const fb = createCopyFeedback();
    await fb.copy('hello');
    expect(get(fb.copied)).toBe(false);
    expect(get(fb.copyFailed)).toBe(true);
  });

  it('flips copyFailed=true when navigator.clipboard is missing', async () => {
    removeClipboard();
    const fb = createCopyFeedback();
    await fb.copy('hello');
    expect(get(fb.copied)).toBe(false);
    expect(get(fb.copyFailed)).toBe(true);
  });

  it('a second copy cancels the first timer so stale resets cannot fire', async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    const fb = createCopyFeedback(1500);
    await fb.copy('a');
    // Advance partially through the first timer.
    vi.advanceTimersByTime(1000);
    // Second copy starts a fresh cycle.
    await fb.copy('b');
    // Advance past the ORIGINAL timer's remaining 500ms. If the first timer
    // weren't cleared, it would now fire and flip copied back to false.
    vi.advanceTimersByTime(500);
    expect(get(fb.copied)).toBe(true);
    // And the fresh 1500ms cycle still resets correctly.
    vi.advanceTimersByTime(1000);
    expect(get(fb.copied)).toBe(false);
  });

  it('destroy() prevents a pending timer from flipping state later', async () => {
    vi.useFakeTimers();
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    const fb = createCopyFeedback(1500);
    await fb.copy('a');
    expect(get(fb.copied)).toBe(true);
    fb.destroy();
    // State is NOT forced to reset by destroy; it just stops the timer.
    // (Component is unmounting; what the stores say after destroy is irrelevant.)
    vi.advanceTimersByTime(5000);
    // The timer must not have run, so copied remains true (no flip).
    expect(get(fb.copied)).toBe(true);
  });
});
