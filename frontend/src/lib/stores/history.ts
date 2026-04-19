import { writable } from 'svelte/store';

export interface HistoryEntry {
  sourceUrl: string;
  title: string;
  artists: string[];
  coverUrl: string | null;
  timestamp: number;
}

const STORAGE_KEY = 'linkhop:history';
const MAX = 20;

function load(): HistoryEntry[] {
  if (typeof localStorage === 'undefined') return [];
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(entries: HistoryEntry[]): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  }
}

export const history = writable<HistoryEntry[]>(load());

export function addHistory(entry: HistoryEntry): void {
  history.update((list) => {
    const filtered = list.filter((e) => e.sourceUrl !== entry.sourceUrl);
    const next = [entry, ...filtered].slice(0, MAX);
    persist(next);
    return next;
  });
}

export function clearHistory(): void {
  history.update(() => {
    persist([]);
    return [];
  });
}
