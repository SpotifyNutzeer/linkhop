import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

describe('theme store', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('defaults to auto when localStorage is empty', async () => {
    const { themePref } = await import('./theme');
    expect(get(themePref)).toBe('auto');
  });

  it('reads persisted pref from localStorage', async () => {
    localStorage.setItem('linkhop:theme', 'dark');
    const { themePref } = await import('./theme');
    expect(get(themePref)).toBe('dark');
  });

  it('setTheme persists and updates data-theme', async () => {
    const { setTheme } = await import('./theme');
    setTheme('light');
    expect(localStorage.getItem('linkhop:theme')).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('auto resolves via matchMedia', async () => {
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: q.includes('dark'),
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {}
    }));
    const { setTheme } = await import('./theme');
    setTheme('auto');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('updates data-theme when system preference changes while in auto mode', async () => {
    let changeCallback: ((e: { matches: boolean }) => void) | null = null;
    let isDark = false;
    vi.stubGlobal('matchMedia', (q: string) => ({
      matches: q.includes('dark') && isDark,
      media: q,
      addEventListener: (_: string, cb: (e: { matches: boolean }) => void) => { changeCallback = cb; },
      removeEventListener: () => {}
    }));
    const { setTheme } = await import('./theme');
    setTheme('auto');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    isDark = true;
    changeCallback?.({ matches: true });
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});
