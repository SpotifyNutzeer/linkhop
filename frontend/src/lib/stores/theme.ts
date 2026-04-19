import { writable, derived, get } from 'svelte/store';

export type Pref = 'auto' | 'dark' | 'light';
export type Effective = 'dark' | 'light';

const STORAGE_KEY = 'linkhop:theme';

function readInitial(): Pref {
  if (typeof localStorage === 'undefined') return 'auto';
  const v = localStorage.getItem(STORAGE_KEY);
  return v === 'dark' || v === 'light' || v === 'auto' ? v : 'auto';
}

export const themePref = writable<Pref>(readInitial());

function resolveEffective(pref: Pref): Effective {
  if (pref === 'dark') return 'dark';
  if (pref === 'light') return 'light';
  if (typeof matchMedia === 'undefined') return 'light';
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export const effectiveTheme = derived(themePref, ($p) => resolveEffective($p));

effectiveTheme.subscribe((eff) => {
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', eff);
  }
});

themePref.subscribe((p) => {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, p);
  }
});

if (typeof matchMedia !== 'undefined') {
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (get(themePref) === 'auto') {
      themePref.set('auto');
    }
  });
}

export function setTheme(p: Pref): void {
  themePref.set(p);
}

export function cycleTheme(): void {
  const p = get(themePref);
  const next: Pref = p === 'auto' ? 'dark' : p === 'dark' ? 'light' : 'auto';
  themePref.set(next);
}
