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

const mql =
  typeof matchMedia !== 'undefined' ? matchMedia('(prefers-color-scheme: dark)') : null;

const systemDark = writable<boolean>(mql?.matches ?? false);

mql?.addEventListener('change', (e) => {
  systemDark.set(e.matches);
});

export const effectiveTheme = derived<[typeof themePref, typeof systemDark], Effective>(
  [themePref, systemDark],
  ([$p, $sys]) => {
    if ($p === 'dark') return 'dark';
    if ($p === 'light') return 'light';
    return $sys ? 'dark' : 'light';
  }
);

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

export function setTheme(p: Pref): void {
  themePref.set(p);
}

export function cycleTheme(): void {
  const p = get(themePref);
  const next: Pref = p === 'auto' ? 'dark' : p === 'dark' ? 'light' : 'auto';
  themePref.set(next);
}
