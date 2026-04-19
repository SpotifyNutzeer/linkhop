import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

describe('history store', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it('is empty when localStorage is empty', async () => {
    const { history } = await import('./history');
    expect(get(history)).toEqual([]);
  });

  it('add prepends entry', async () => {
    const { history, addHistory } = await import('./history');
    addHistory({ sourceUrl: 'a', title: 'A', artists: [], coverUrl: null, timestamp: 1 });
    expect(get(history).length).toBe(1);
    expect(get(history)[0].sourceUrl).toBe('a');
  });

  it('dedupes by sourceUrl', async () => {
    const { history, addHistory } = await import('./history');
    addHistory({ sourceUrl: 'a', title: 'A1', artists: [], coverUrl: null, timestamp: 1 });
    addHistory({ sourceUrl: 'b', title: 'B', artists: [], coverUrl: null, timestamp: 2 });
    addHistory({ sourceUrl: 'a', title: 'A2', artists: [], coverUrl: null, timestamp: 3 });
    const h = get(history);
    expect(h.length).toBe(2);
    expect(h[0].sourceUrl).toBe('a');
    expect(h[0].title).toBe('A2');
    expect(h[1].sourceUrl).toBe('b');
  });

  it('caps at 20', async () => {
    const { history, addHistory } = await import('./history');
    for (let i = 0; i < 25; i++) {
      addHistory({ sourceUrl: `u${i}`, title: `T${i}`, artists: [], coverUrl: null, timestamp: i });
    }
    expect(get(history).length).toBe(20);
    expect(get(history)[0].sourceUrl).toBe('u24');
  });

  it('persists to localStorage', async () => {
    const { addHistory } = await import('./history');
    addHistory({ sourceUrl: 'a', title: 'A', artists: [], coverUrl: null, timestamp: 1 });
    expect(localStorage.getItem('linkhop:history')).toContain('"sourceUrl":"a"');
  });

  it('tolerates corrupt localStorage', async () => {
    localStorage.setItem('linkhop:history', '{not json');
    const { history } = await import('./history');
    expect(get(history)).toEqual([]);
  });

  it('clearHistory empties', async () => {
    const { history, addHistory, clearHistory } = await import('./history');
    addHistory({ sourceUrl: 'a', title: 'A', artists: [], coverUrl: null, timestamp: 1 });
    clearHistory();
    expect(get(history)).toEqual([]);
    expect(localStorage.getItem('linkhop:history')).toBe('[]');
  });
});
