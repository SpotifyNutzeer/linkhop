# linkhop Frontend Implementation Plan (Plan C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Baue das SvelteKit-Frontend für linkhop (statisch gebaut, Nginx-ausgeliefert) mit Theme-Toggle, History, Share-Flow, Short-Link-Route, Docker-Image und CI, gemäß der V1- und Frontend-Spec.

**Architecture:** Single-Page-SvelteKit-App mit `adapter-static` + `fallback: "index.html"`. Statisch gebaut, vom Nginx-Alpine-Container ausgeliefert. Konsumiert nur `/api/v1/*` (Traefik routet) — kein Backend-for-Frontend. Drei Svelte-Stores (`theme`, `history`, `services`), dünner `fetch`-Client, CSS-Custom-Property-Tokens (Catppuccin Mocha/Latte). Tests in drei Ebenen (Vitest Unit, Testing-Library Component, Playwright E2E + axe).

**Tech Stack:** SvelteKit 2 + Svelte 5 + TypeScript, Vite, pnpm, `@sveltejs/adapter-static`, `openapi-typescript`, Vitest, `@testing-library/svelte`, MSW, Playwright, `@axe-core/playwright`, Nginx Alpine, Docker multi-stage, GitHub Actions.

**Referenz-Specs:**
- `docs/superpowers/specs/2026-04-18-linkhop-design.md` (V1-Master)
- `docs/superpowers/specs/2026-04-19-linkhop-frontend-design.md` (Frontend-Detail)

---

## File Structure

```
linkconverter/
├── backend/                                # bestehend — nicht angefasst
├── frontend/                               # NEU
│   ├── src/
│   │   ├── app.html                        # FOUC-Schutz-Script, root
│   │   ├── app.d.ts                        # SvelteKit-Typen
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   │   ├── client.ts               # convert/lookup/services + ApiError
│   │   │   │   ├── schema.d.ts             # generiert via openapi-typescript, committed
│   │   │   │   └── types.ts                # abgeleitete Response-Typen
│   │   │   ├── components/
│   │   │   │   ├── Header.svelte
│   │   │   │   ├── ThemeToggle.svelte
│   │   │   │   ├── InputBar.svelte
│   │   │   │   ├── HistoryDropdown.svelte
│   │   │   │   ├── ResultCard.svelte
│   │   │   │   ├── ServiceList.svelte
│   │   │   │   ├── ServiceItem.svelte
│   │   │   │   ├── ShareButton.svelte
│   │   │   │   ├── ErrorPanel.svelte
│   │   │   │   └── Skeleton.svelte
│   │   │   ├── stores/
│   │   │   │   ├── theme.ts
│   │   │   │   ├── history.ts
│   │   │   │   └── services.ts
│   │   │   └── theme/
│   │   │       └── tokens.css              # Catppuccin Mocha/Latte Custom Properties
│   │   ├── routes/
│   │   │   ├── +layout.svelte              # Header + /services-Load
│   │   │   ├── +layout.ts                  # load-Function
│   │   │   ├── +page.svelte                # Home (Input, Result, History, ?url=-Autoload)
│   │   │   └── c/[shortId]/+page.svelte    # Short-Link-Viewer
│   │   └── test/
│   │       └── setup.ts                    # Vitest + MSW-Setup
│   ├── tests/
│   │   └── e2e/
│   │       └── smoke.spec.ts               # Playwright
│   ├── static/
│   │   └── favicon.svg                     # Lavender-Punkt
│   ├── Dockerfile                          # multi-stage node → nginx
│   ├── nginx.conf                          # SPA-fallback + asset-caching
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── svelte.config.js                    # adapter-static, fallback: index.html
│   ├── vite.config.ts                      # server.proxy /api → :8080
│   ├── playwright.config.ts
│   ├── tsconfig.json
│   └── .nvmrc
└── .github/workflows/
    └── frontend.yml                        # NEU (neben bestehendem backend.yml)
```

---

## Task 1: Scaffold — SvelteKit + adapter-static + pnpm

**Ziel:** Ein leeres SvelteKit-Projekt, das `pnpm dev` startet, `pnpm build` als statisches Bundle nach `frontend/build/` erzeugt, `pnpm test` Vitest läuft und einen trivialen Sanity-Test bestanden hat.

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/pnpm-lock.yaml` (via `pnpm install`)
- Create: `frontend/svelte.config.js`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/.nvmrc`
- Create: `frontend/src/app.html`
- Create: `frontend/src/app.d.ts`
- Create: `frontend/src/routes/+page.svelte`
- Create: `frontend/src/lib/sanity.ts`
- Create: `frontend/src/lib/sanity.test.ts`
- Create: `frontend/src/test/setup.ts`

- [ ] **Step 1: Verzeichnis anlegen und pnpm initialisieren**

```bash
mkdir -p frontend && cd frontend
pnpm init
```

- [ ] **Step 2: `frontend/package.json` schreiben**

```json
{
  "name": "linkhop-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22" },
  "packageManager": "pnpm@10.33.0",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-check --tsconfig ./tsconfig.json",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "@sveltejs/adapter-static": "^3.0.0",
    "@sveltejs/kit": "^2.5.0",
    "@sveltejs/vite-plugin-svelte": "^3.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/svelte": "^4.0.0",
    "@testing-library/user-event": "^14.5.0",
    "jsdom": "^24.0.0",
    "svelte": "^4.2.0",
    "svelte-check": "^3.6.0",
    "tslib": "^2.6.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.6.0"
  }
}
```

- [ ] **Step 3: `frontend/svelte.config.js` schreiben**

```js
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html',
      precompress: false,
      strict: true
    })
  }
};
```

- [ ] **Step 4: `frontend/vite.config.ts` schreiben**

```ts
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8080'
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.ts']
  }
});
```

- [ ] **Step 5: `frontend/tsconfig.json` schreiben**

```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "allowJs": false,
    "checkJs": false,
    "strict": true,
    "moduleResolution": "bundler"
  }
}
```

- [ ] **Step 6: `frontend/.nvmrc` schreiben**

```
22
```

- [ ] **Step 7: `frontend/src/app.html` schreiben**

```html
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.svg" type="image/svg+xml" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>linkhop</title>
    %sveltekit.head%
  </head>
  <body data-sveltekit-preload-data="hover">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
```

- [ ] **Step 8: `frontend/src/app.d.ts` schreiben**

```ts
declare global {
  namespace App {}
}
export {};
```

- [ ] **Step 9: `frontend/src/routes/+page.svelte` schreiben (Scaffold-Placeholder)**

```svelte
<h1>linkhop.</h1>
<p>Frontend-Scaffold läuft.</p>
```

- [ ] **Step 10: `frontend/src/test/setup.ts` schreiben**

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 11: Sanity-Test schreiben**

`frontend/src/lib/sanity.ts`:

```ts
export function sanity(): string {
  return 'linkhop';
}
```

`frontend/src/lib/sanity.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { sanity } from './sanity';

describe('sanity', () => {
  it('returns linkhop', () => {
    expect(sanity()).toBe('linkhop');
  });
});
```

- [ ] **Step 12: Dependencies installieren**

Run: `cd frontend && pnpm install`
Expected: `pnpm-lock.yaml` entsteht, keine Fehler.

- [ ] **Step 13: Sanity-Test laufen lassen**

Run: `cd frontend && pnpm test`
Expected: `1 passed`.

- [ ] **Step 14: Build smoke-testen**

Run: `cd frontend && pnpm build`
Expected: `build/index.html` existiert.

- [ ] **Step 15: `.gitignore` aktualisieren**

In `frontend/.gitignore` (neu anlegen):

```
node_modules
.svelte-kit
build
.env
```

- [ ] **Step 16: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold SvelteKit with adapter-static and Vitest"
```

---

## Task 2: Theme-System — Tokens, FOUC-Schutz, Store, Toggle

**Ziel:** Catppuccin Mocha/Latte-Themes via `data-theme`-Attribut auf `<html>`. FOUC-Schutz via Inline-Script. Persistenter `theme`-Store mit `auto`-Modus. `ThemeToggle`-Component mit zyklischem Zustand.

**Files:**
- Create: `frontend/src/lib/theme/tokens.css`
- Create: `frontend/src/lib/stores/theme.ts`
- Create: `frontend/src/lib/stores/theme.test.ts`
- Create: `frontend/src/lib/components/ThemeToggle.svelte`
- Create: `frontend/src/lib/components/ThemeToggle.test.ts`
- Modify: `frontend/src/app.html` (FOUC-Script einfügen)
- Modify: `frontend/src/routes/+page.svelte` (tokens.css importieren, Tokens verwenden)

- [ ] **Step 1: Token-CSS schreiben**

`frontend/src/lib/theme/tokens.css`:

```css
:root[data-theme="dark"] {
  --bg: #1e1e2e;
  --bg-surface: #313244;
  --text: #cdd6f4;
  --text-muted: #bac2de;
  --accent: #b4befe;
  --success: #a6e3a1;
  --warning: #f9e2af;
  --error: #f38ba8;
  --border: #45475a;
}
:root[data-theme="light"] {
  --bg: #eff1f5;
  --bg-surface: #ccd0da;
  --text: #4c4f69;
  --text-muted: #5c5f77;
  --accent: #7287fd;
  --success: #40a02b;
  --warning: #df8e1d;
  --error: #d20f39;
  --border: #bcc0cc;
}
:root {
  color-scheme: light dark;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
}
html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}
```

- [ ] **Step 2: FOUC-Schutz-Script in `app.html` einfügen**

In `frontend/src/app.html` direkt nach `<meta name="viewport" ...>` einfügen:

```html
<script>
(function(){
  var p=localStorage.getItem('linkhop:theme')||'auto';
  var d=p==='dark'||(p==='auto'&&matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme',d?'dark':'light');
})();
</script>
```

- [ ] **Step 3: Failing Test für `theme`-Store schreiben**

`frontend/src/lib/stores/theme.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

describe('theme store', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    vi.resetModules();
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
});
```

- [ ] **Step 4: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/stores/theme.test.ts`
Expected: FAIL — Modul existiert nicht.

- [ ] **Step 5: `theme`-Store implementieren**

`frontend/src/lib/stores/theme.ts`:

```ts
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
```

- [ ] **Step 6: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/stores/theme.test.ts`
Expected: alle 4 Tests PASS.

- [ ] **Step 7: `ThemeToggle`-Component schreiben**

`frontend/src/lib/components/ThemeToggle.svelte`:

```svelte
<script lang="ts">
  import { themePref, cycleTheme, type Pref } from '$lib/stores/theme';

  const icons: Record<Pref, string> = { auto: '🌓', dark: '🌙', light: '☀️' };
  const labels: Record<Pref, string> = {
    auto: 'Theme: automatisch, zum Wechseln klicken',
    dark: 'Theme: dunkel, zum Wechseln klicken',
    light: 'Theme: hell, zum Wechseln klicken'
  };
</script>

<button
  type="button"
  class="theme-toggle"
  aria-label={labels[$themePref]}
  on:click={cycleTheme}
>
  {icons[$themePref]}
</button>

<style>
  .theme-toggle {
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    cursor: pointer;
    font-size: 1.2rem;
    padding: 0.4rem 0.6rem;
  }
  .theme-toggle:hover { background: var(--bg-surface); }
</style>
```

- [ ] **Step 8: Failing Component-Test für ThemeToggle schreiben**

`frontend/src/lib/components/ThemeToggle.test.ts`:

```ts
import { beforeEach, describe, expect, it } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ThemeToggle from './ThemeToggle.svelte';

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('cycles auto → dark → light → auto on click', async () => {
    const { getByRole } = render(ThemeToggle);
    const btn = getByRole('button');
    expect(btn.getAttribute('aria-label')).toContain('automatisch');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toContain('dunkel');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toContain('hell');
    await fireEvent.click(btn);
    expect(btn.getAttribute('aria-label')).toContain('automatisch');
  });
});
```

- [ ] **Step 9: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/components/ThemeToggle.test.ts`
Expected: PASS.

- [ ] **Step 10: tokens.css global importieren**

`frontend/src/routes/+layout.svelte` neu anlegen:

```svelte
<script lang="ts">
  import '$lib/theme/tokens.css';
</script>

<slot />
```

- [ ] **Step 11: Komplette Test-Suite laufen lassen**

Run: `cd frontend && pnpm test`
Expected: alle Tests PASS.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/lib/theme frontend/src/lib/stores/theme.ts frontend/src/lib/stores/theme.test.ts \
        frontend/src/lib/components/ThemeToggle.svelte frontend/src/lib/components/ThemeToggle.test.ts \
        frontend/src/app.html frontend/src/routes/+layout.svelte
git commit -m "feat(frontend): theme system with Catppuccin tokens, FOUC guard, toggle"
```

---

## Task 3: API-Client + Schema-Generation

**Ziel:** `openapi-typescript` generiert `schema.d.ts` aus dem Backend-OpenAPI, `pnpm gen:api` als npm-Script, committed Schema, dünner Fetch-Wrapper mit `ApiError`. Unit-Tests mit MSW.

**Files:**
- Create: `frontend/src/lib/api/client.ts`
- Create: `frontend/src/lib/api/client.test.ts`
- Create: `frontend/src/lib/api/types.ts`
- Create: `frontend/src/lib/api/schema.d.ts` (via `pnpm gen:api`)
- Modify: `frontend/package.json` (Scripts + Dependencies)
- Modify: `frontend/src/test/setup.ts` (MSW-Server-Setup)

- [ ] **Step 1: Dependencies hinzufügen**

Run:
```bash
cd frontend
pnpm add -D openapi-typescript msw
```

- [ ] **Step 2: npm-Scripts erweitern**

In `frontend/package.json` im `scripts`-Block ergänzen:

```json
{
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-check --tsconfig ./tsconfig.json",
    "test": "vitest run",
    "test:watch": "vitest",
    "gen:api": "openapi-typescript ../backend/openapi.json -o src/lib/api/schema.d.ts",
    "predev": "pnpm gen:api",
    "prebuild": "pnpm gen:api"
  }
}
```

- [ ] **Step 3: Backend-OpenAPI als JSON exportieren**

Run (aus Repo-Root):
```bash
cd backend && python -c "from linkhop.main import app; import json, sys; json.dump(app.openapi(), open('openapi.json', 'w'), indent=2)"
```
Expected: `backend/openapi.json` existiert.

- [ ] **Step 4: Schema generieren**

Run:
```bash
cd frontend && pnpm gen:api
```
Expected: `frontend/src/lib/api/schema.d.ts` mit Inhalt.

- [ ] **Step 5: Abgeleitete Typen in `types.ts`**

`frontend/src/lib/api/types.ts`:

```ts
import type { components } from './schema';

export type ConvertResponse = components['schemas']['ConvertResponse'];
export type ServicesResponse = components['schemas']['ServicesResponse'];
export type ServiceInfo = components['schemas']['ServiceInfo'];
export type TargetResult = components['schemas']['TargetResult'];

export type ApiErrorCode =
  | 'invalid_url'
  | 'unsupported_service'
  | 'not_found'
  | 'rate_limited'
  | 'server_error'
  | 'offline';

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    public readonly status: number,
    message: string,
    public readonly sourceUrl?: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
```

Falls Schema-Typ-Namen abweichen (z. B. Backend nennt sie anders), an konkrete Namen in `schema.d.ts` anpassen.

- [ ] **Step 6: Failing Test für API-Client schreiben**

`frontend/src/lib/api/client.test.ts`:

```ts
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { convert, lookup, services, ApiError } from './client';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Glob-Match (`*/api/v1/…`) statt konkretem Host: JSDOM löst relative Fetches
// gegen den vitest-Base-Host auf, der Test muss sich nicht darum kümmern.
describe('api client', () => {
  it('convert returns response on 200', async () => {
    server.use(
      http.get('*/api/v1/convert', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('url')).toBe('https://example.com/track/1');
        return HttpResponse.json({ source: { service: 'tidal' }, targets: {} });
      })
    );
    const res = await convert('https://example.com/track/1');
    expect(res.source.service).toBe('tidal');
  });

  it('convert throws ApiError with mapped code on 400', async () => {
    server.use(
      http.get('*/api/v1/convert', () =>
        HttpResponse.json({ code: 'invalid_url', message: 'bad' }, { status: 400 })
      )
    );
    await expect(convert('https://bad')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'invalid_url',
      status: 400
    });
  });

  it('convert throws ApiError offline on network exception', async () => {
    server.use(http.get('*/api/v1/convert', () => HttpResponse.error()));
    await expect(convert('https://x')).rejects.toMatchObject({ code: 'offline' });
  });

  it('convert passes share=true', async () => {
    server.use(
      http.get('*/api/v1/convert', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('share')).toBe('true');
        return HttpResponse.json({ source: {}, targets: {}, share: { id: 'ab3x9k' } });
      })
    );
    await convert('https://x', { share: true });
  });

  it('lookup GETs /c/<id>', async () => {
    server.use(
      http.get('*/api/v1/c/ab3x9k', () =>
        HttpResponse.json({ source: { service: 'spotify' }, targets: {} })
      )
    );
    const res = await lookup('ab3x9k');
    expect(res.source.service).toBe('spotify');
  });

  it('lookup 404 maps to not_found code', async () => {
    server.use(
      http.get('*/api/v1/c/missing', () =>
        HttpResponse.json({ code: 'not_found', message: 'nope' }, { status: 404 })
      )
    );
    await expect(lookup('missing')).rejects.toMatchObject({ code: 'not_found' });
  });

  it('services returns map', async () => {
    server.use(
      http.get('*/api/v1/services', () =>
        HttpResponse.json({ services: { spotify: { name: 'Spotify', capabilities: ['track'] } } })
      )
    );
    const res = await services();
    expect(res.services.spotify.name).toBe('Spotify');
  });
});
```

- [ ] **Step 7: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/api/client.test.ts`
Expected: FAIL — `client.ts` existiert nicht.

- [ ] **Step 8: `client.ts` implementieren**

`frontend/src/lib/api/client.ts`:

```ts
import { ApiError, type ApiErrorCode, type ConvertResponse, type ServicesResponse } from './types';

const BASE = '/api/v1';

function mapStatus(status: number, code: string | undefined): ApiErrorCode {
  if (code === 'invalid_url' || code === 'unsupported_service') return code;
  if (code === 'rate_limited' || status === 429) return 'rate_limited';
  if (status === 404) return 'not_found';
  if (status >= 500) return 'server_error';
  if (status === 400) return 'invalid_url';
  return 'server_error';
}

async function request<T>(path: string, opts?: { sourceUrl?: string; signal?: AbortSignal }): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { signal: opts?.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new ApiError('offline', 0, 'Keine Verbindung zum Server', opts?.sourceUrl);
  }
  if (!res.ok) {
    let body: { code?: string; message?: string } = {};
    try { body = await res.json(); } catch { /* body leer / kein JSON */ }
    throw new ApiError(
      mapStatus(res.status, body.code),
      res.status,
      body.message ?? res.statusText,
      opts?.sourceUrl
    );
  }
  return res.json() as Promise<T>;
}

export async function convert(
  url: string,
  opts: { share?: boolean; targets?: string[]; signal?: AbortSignal } = {}
): Promise<ConvertResponse> {
  const qs = new URLSearchParams({ url });
  if (opts.share) qs.set('share', 'true');
  if (opts.targets?.length) qs.set('targets', opts.targets.join(','));
  return request<ConvertResponse>(`${BASE}/convert?${qs}`, { sourceUrl: url, signal: opts.signal });
}

export async function lookup(shortId: string): Promise<ConvertResponse> {
  return request<ConvertResponse>(`${BASE}/c/${encodeURIComponent(shortId)}`);
}

export async function services(): Promise<ServicesResponse> {
  return request<ServicesResponse>(`${BASE}/services`);
}

export { ApiError } from './types';
```

- [ ] **Step 9: MSW-Server im Test-Setup aktivieren**

In `frontend/src/test/setup.ts` ergänzen (am Ende):

```ts
import '@testing-library/jest-dom/vitest';
```

(MSW wird in `client.test.ts` selbst gestartet; das Setup bleibt minimal. Falls andere Tests MSW brauchen, wird es dort gestartet.)

- [ ] **Step 10: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/api/client.test.ts`
Expected: alle 7 Tests PASS.

- [ ] **Step 11: `backend/openapi.json` in `backend/.gitignore` aufnehmen**

Falls `backend/.gitignore` bereits existiert, `openapi.json` ergänzen. Grund: Das File ist ein Build-Artefakt und wird im CI frisch exportiert.

- [ ] **Step 12: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml \
        frontend/src/lib/api/ \
        frontend/src/test/setup.ts \
        backend/.gitignore
git commit -m "feat(frontend): API client with generated schema and MSW-backed tests"
```

---

## Task 4: Stores — history, services

**Ziel:** `history`-Store (add/dedupe/cap-20/clear, localStorage-persistiert), `services`-Store (initial leer). Unit-Tests decken Deduplizierung, Cap, korrupte Daten.

**Files:**
- Create: `frontend/src/lib/stores/history.ts`
- Create: `frontend/src/lib/stores/history.test.ts`
- Create: `frontend/src/lib/stores/services.ts`
- Create: `frontend/src/lib/stores/services.test.ts`

- [ ] **Step 1: Failing Test für `history`-Store schreiben**

`frontend/src/lib/stores/history.test.ts`:

```ts
import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';

describe('history store', () => {
  beforeEach(async () => {
    localStorage.clear();
    const mod = await import('./history');
    mod.history.set([]);
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
    const mod = await import('./history');
    // Store reload: force re-read
    expect(get(mod.history)).toEqual([]);
  });

  it('clearHistory empties', async () => {
    const { history, addHistory, clearHistory } = await import('./history');
    addHistory({ sourceUrl: 'a', title: 'A', artists: [], coverUrl: null, timestamp: 1 });
    clearHistory();
    expect(get(history)).toEqual([]);
    expect(localStorage.getItem('linkhop:history')).toBe('[]');
  });
});
```

Hinweis: Wegen `vi.resetModules()` oder `dynamic imports` in Tests kann `import('./history')` zwischen Tests cached werden. Alternativ `vi.resetModules()` in `beforeEach` aufrufen, wenn Tests kollidieren.

- [ ] **Step 2: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/stores/history.test.ts`
Expected: FAIL.

- [ ] **Step 3: `history`-Store implementieren**

`frontend/src/lib/stores/history.ts`:

```ts
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
  history.set([]);
  persist([]);
}
```

- [ ] **Step 4: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/stores/history.test.ts`
Expected: alle 7 Tests PASS. Falls „tolerates corrupt localStorage" wegen Module-Caching fehlschlägt, in `beforeEach` `vi.resetModules()` ergänzen.

- [ ] **Step 5: `services`-Store implementieren**

`frontend/src/lib/stores/services.ts`:

```ts
import { writable } from 'svelte/store';
import type { ServiceInfo } from '$lib/api/types';

export const services = writable<Record<string, ServiceInfo>>({});
```

Hinweis: Der Store speichert einen Record (`id → ServiceInfo`), weil Consumer (Task 6 `ServiceItem`) per Service-ID zugreifen. Das Backend liefert ein Array — die Array→Record-Umwandlung passiert in Task 5 beim `/services`-Load.

`frontend/src/lib/stores/services.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import { services } from './services';

describe('services store', () => {
  it('starts empty', () => {
    expect(get(services)).toEqual({});
  });
  it('can be set', () => {
    services.set({
      spotify: { id: 'spotify', name: 'Spotify', capabilities: ['track'] }
    });
    expect(get(services).spotify.name).toBe('Spotify');
  });
});
```

- [ ] **Step 6: Komplette Suite laufen lassen**

Run: `cd frontend && pnpm test`
Expected: alle Tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/stores/history.ts frontend/src/lib/stores/history.test.ts \
        frontend/src/lib/stores/services.ts frontend/src/lib/stores/services.test.ts
git commit -m "feat(frontend): history store with dedupe/cap and services store"
```

---

## Task 5: Layout + Header + InputBar + HistoryDropdown

**Ziel:** `+layout.svelte` lädt `/services` beim Mount. `Header` zeigt Wort-Mark + Theme-Toggle. `InputBar` feuert `submit`-Event. `HistoryDropdown` zeigt Einträge beim Focus.

**Files:**
- Modify: `frontend/src/routes/+layout.svelte`
- Create: `frontend/src/routes/+layout.ts`
- Create: `frontend/src/lib/components/Header.svelte`
- Create: `frontend/src/lib/components/InputBar.svelte`
- Create: `frontend/src/lib/components/InputBar.test.ts`
- Create: `frontend/src/lib/components/HistoryDropdown.svelte`
- Create: `frontend/src/lib/components/HistoryDropdown.test.ts`

- [ ] **Step 1: `Header.svelte` schreiben**

`frontend/src/lib/components/Header.svelte`:

```svelte
<script lang="ts">
  import ThemeToggle from './ThemeToggle.svelte';
</script>

<header class="hdr">
  <span class="brand">linkhop.</span>
  <ThemeToggle />
</header>

<style>
  .hdr {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border);
  }
  .brand {
    color: var(--accent);
    font-weight: 700;
    font-size: 1.4rem;
    letter-spacing: -0.02em;
  }
</style>
```

- [ ] **Step 2: `+layout.svelte` mit Header + /services-Load**

`frontend/src/routes/+layout.svelte` ersetzen:

```svelte
<script lang="ts">
  import '$lib/theme/tokens.css';
  import Header from '$lib/components/Header.svelte';
  import { onMount } from 'svelte';
  import { services as servicesStore } from '$lib/stores/services';
  import { services as fetchServices } from '$lib/api/client';

  onMount(async () => {
    try {
      const res = await fetchServices();
      const map = Object.fromEntries(res.services.map((s) => [s.id, s]));
      servicesStore.set(map);
    } catch {
      // Services-Load ist Best-Effort: bei Fehler bleibt die Map leer,
      // ServiceItem fällt auf Service-ID als Display-Name zurück.
    }
  });
</script>

<Header />
<main>
  <slot />
</main>

<style>
  main {
    max-width: 960px;
    margin: 0 auto;
    padding: 1.5rem;
  }
</style>
```

- [ ] **Step 3: Failing Test für `InputBar` schreiben**

`frontend/src/lib/components/InputBar.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import InputBar from './InputBar.svelte';

describe('InputBar', () => {
  it('dispatches submit with url on button click', async () => {
    const handler = vi.fn();
    const { getByRole, component } = render(InputBar);
    component.$on('submit', (e: CustomEvent) => handler(e.detail));
    const input = getByRole('textbox');
    await fireEvent.input(input, { target: { value: 'https://x' } });
    await fireEvent.click(getByRole('button', { name: /konvertieren/i }));
    expect(handler).toHaveBeenCalledWith({ url: 'https://x' });
  });

  it('dispatches submit on Enter', async () => {
    const handler = vi.fn();
    const { getByRole, component } = render(InputBar);
    component.$on('submit', (e: CustomEvent) => handler(e.detail));
    const input = getByRole('textbox');
    await fireEvent.input(input, { target: { value: 'https://y' } });
    await fireEvent.keyDown(input, { key: 'Enter' });
    expect(handler).toHaveBeenCalledWith({ url: 'https://y' });
  });

  it('does not submit empty value', async () => {
    const handler = vi.fn();
    const { getByRole, component } = render(InputBar);
    component.$on('submit', (e: CustomEvent) => handler(e.detail));
    await fireEvent.click(getByRole('button', { name: /konvertieren/i }));
    expect(handler).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 4: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/components/InputBar.test.ts`
Expected: FAIL.

- [ ] **Step 5: `InputBar.svelte` implementieren**

`frontend/src/lib/components/InputBar.svelte`:

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let value = '';
  export let disabled = false;

  const dispatch = createEventDispatcher<{
    submit: { url: string };
    focus: void;
    blur: void;
  }>();

  function submit() {
    const trimmed = value.trim();
    if (!trimmed) return;
    dispatch('submit', { url: trimmed });
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter') submit();
  }
</script>

<div class="bar">
  <input
    type="url"
    role="textbox"
    placeholder="Spotify-, Deezer- oder Tidal-Link einfügen …"
    bind:value
    on:keydown={onKeyDown}
    on:focus={() => dispatch('focus')}
    on:blur={() => dispatch('blur')}
    aria-label="Streaming-Link"
    {disabled}
  />
  <button type="button" on:click={submit} {disabled}>Konvertieren</button>
</div>

<style>
  .bar {
    display: flex;
    gap: 0.5rem;
    align-items: stretch;
  }
  input {
    flex: 1;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    background: var(--bg-surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  button {
    background: var(--accent);
    color: var(--bg);
    border: none;
    border-radius: 6px;
    padding: 0 1.25rem;
    cursor: pointer;
    font-weight: 600;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
```

- [ ] **Step 6: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/components/InputBar.test.ts`
Expected: 3 Tests PASS.

- [ ] **Step 7: Failing Test für `HistoryDropdown` schreiben**

`frontend/src/lib/components/HistoryDropdown.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import HistoryDropdown from './HistoryDropdown.svelte';
import { history } from '$lib/stores/history';

describe('HistoryDropdown', () => {
  beforeEach(() => history.set([]));

  it('renders nothing when empty', () => {
    const { container } = render(HistoryDropdown, { props: { open: true } });
    expect(container.querySelector('.dropdown')).toBeNull();
  });

  it('renders entries when open and non-empty', () => {
    history.set([
      { sourceUrl: 'https://a', title: 'Nightcall', artists: ['Kavinsky'], coverUrl: null, timestamp: 1 }
    ]);
    const { getByText } = render(HistoryDropdown, { props: { open: true } });
    expect(getByText('Nightcall')).toBeInTheDocument();
  });

  it('dispatches select on click', async () => {
    history.set([
      { sourceUrl: 'https://a', title: 'T', artists: [], coverUrl: null, timestamp: 1 }
    ]);
    const handler = vi.fn();
    const { getByRole, component } = render(HistoryDropdown, { props: { open: true } });
    component.$on('select', (e: CustomEvent) => handler(e.detail));
    await fireEvent.click(getByRole('button', { name: /T/ }));
    expect(handler).toHaveBeenCalledWith({ url: 'https://a' });
  });
});
```

- [ ] **Step 8: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/components/HistoryDropdown.test.ts`
Expected: FAIL.

- [ ] **Step 9: `HistoryDropdown.svelte` implementieren**

`frontend/src/lib/components/HistoryDropdown.svelte`:

```svelte
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { history, clearHistory } from '$lib/stores/history';

  export let open = false;

  const dispatch = createEventDispatcher<{ select: { url: string } }>();

  function select(url: string) {
    dispatch('select', { url });
  }

  function truncate(url: string, n = 40) {
    return url.length > n ? url.slice(0, n - 1) + '…' : url;
  }
</script>

{#if open && $history.length > 0}
  <div class="dropdown" role="listbox" aria-label="Verlauf">
    <div class="hint">Zuletzt:</div>
    {#each $history as entry (entry.sourceUrl)}
      <button
        type="button"
        class="item"
        role="option"
        aria-label={entry.title}
        on:mousedown|preventDefault={() => select(entry.sourceUrl)}
      >
        <span class="title">{entry.title}</span>
        {#if entry.artists.length}<span class="artists">— {entry.artists.join(', ')}</span>{/if}
        <span class="url">{truncate(entry.sourceUrl)}</span>
      </button>
    {/each}
    <div class="footer">
      <button type="button" class="clear" on:mousedown|preventDefault={clearHistory}>Verlauf leeren</button>
    </div>
  </div>
{/if}

<style>
  .dropdown {
    border: 1px solid var(--border);
    border-top: none;
    border-radius: 0 0 6px 6px;
    background: var(--bg-surface);
    padding: 0.5rem;
    max-height: 16rem;
    overflow-y: auto;
  }
  .hint { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.25rem; }
  .item {
    display: flex;
    gap: 0.5rem;
    background: transparent;
    border: none;
    color: var(--text);
    padding: 0.4rem 0.5rem;
    width: 100%;
    text-align: left;
    cursor: pointer;
    border-radius: 4px;
    align-items: baseline;
  }
  .item:hover { background: var(--bg); }
  .title { font-weight: 600; }
  .artists { color: var(--text-muted); }
  .url { color: var(--text-muted); font-size: 0.8rem; margin-left: auto; }
  .footer { border-top: 1px solid var(--border); padding-top: 0.25rem; margin-top: 0.25rem; text-align: right; }
  .clear { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 0.8rem; }
  .clear:hover { color: var(--error); }
</style>
```

- [ ] **Step 10: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/components/HistoryDropdown.test.ts`
Expected: 3 Tests PASS.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/routes/+layout.svelte \
        frontend/src/lib/components/Header.svelte \
        frontend/src/lib/components/InputBar.svelte frontend/src/lib/components/InputBar.test.ts \
        frontend/src/lib/components/HistoryDropdown.svelte frontend/src/lib/components/HistoryDropdown.test.ts
git commit -m "feat(frontend): Header, InputBar, HistoryDropdown with services auto-load"
```

---

## Task 6: ResultCard + ServiceList + ServiceItem + Skeleton

**Ziel:** `ResultCard` stellt Source-Preview + `ServiceList` dar (Desktop Layout C, Mobile Layout B). `ServiceItem` rendert ok / ~match / not_found / error korrekt mit Copy-Link-Button. `Skeleton` als Loading-Platzhalter.

**Files:**
- Create: `frontend/src/lib/components/ResultCard.svelte`
- Create: `frontend/src/lib/components/ServiceList.svelte`
- Create: `frontend/src/lib/components/ServiceItem.svelte`
- Create: `frontend/src/lib/components/ServiceItem.test.ts`
- Create: `frontend/src/lib/components/Skeleton.svelte`

- [ ] **Step 1: Failing Test für `ServiceItem` schreiben**

`frontend/src/lib/components/ServiceItem.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ServiceItem from './ServiceItem.svelte';

describe('ServiceItem', () => {
  it('renders ok link', () => {
    const { getByRole, queryByText } = render(ServiceItem, {
      props: {
        serviceId: 'spotify',
        displayName: 'Spotify',
        result: { status: 'ok', url: 'https://open.spotify.com/track/1', confidence: 0.95 }
      }
    });
    const link = getByRole('link');
    expect(link.getAttribute('href')).toBe('https://open.spotify.com/track/1');
    expect(queryByText(/~match/i)).toBeNull();
  });

  it('shows ~match badge for confidence 0.4–0.7', () => {
    const { getByText } = render(ServiceItem, {
      props: {
        serviceId: 'deezer',
        displayName: 'Deezer',
        result: { status: 'ok', url: 'https://deezer.com/track/2', confidence: 0.55 }
      }
    });
    expect(getByText(/~match/i)).toBeInTheDocument();
  });

  it('shows not_found state', () => {
    const { getByText, queryByRole } = render(ServiceItem, {
      props: {
        serviceId: 'tidal',
        displayName: 'Tidal',
        result: { status: 'not_found' }
      }
    });
    expect(getByText(/nicht gefunden/i)).toBeInTheDocument();
    expect(queryByRole('link')).toBeNull();
  });

  it('shows error state', () => {
    const { getByText } = render(ServiceItem, {
      props: {
        serviceId: 'tidal',
        displayName: 'Tidal',
        result: { status: 'error' }
      }
    });
    expect(getByText(/fehler/i)).toBeInTheDocument();
  });

  it('copy button writes url to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const { getByRole } = render(ServiceItem, {
      props: {
        serviceId: 'spotify',
        displayName: 'Spotify',
        result: { status: 'ok', url: 'https://x', confidence: 0.9 }
      }
    });
    await fireEvent.click(getByRole('button', { name: /kopieren/i }));
    expect(writeText).toHaveBeenCalledWith('https://x');
  });
});
```

- [ ] **Step 2: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/components/ServiceItem.test.ts`
Expected: FAIL.

- [ ] **Step 3: `ServiceItem.svelte` implementieren**

`frontend/src/lib/components/ServiceItem.svelte`:

```svelte
<script lang="ts">
  export let serviceId: string;
  export let displayName: string;
  export let result: {
    status: 'ok' | 'not_found' | 'error';
    url?: string;
    confidence?: number;
  };
  export let isSource = false;

  let copied = false;
  async function copy() {
    if (!result.url) return;
    await navigator.clipboard.writeText(result.url);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }

  $: looseMatch = result.status === 'ok'
    && typeof result.confidence === 'number'
    && result.confidence < 0.7;
</script>

<div class="row" data-service={serviceId}>
  <span class="name">
    {displayName}
    {#if isSource}<span class="badge source">(Quelle)</span>{/if}
  </span>

  {#if result.status === 'ok' && result.url}
    <a class="link" href={result.url} target="_blank" rel="noopener noreferrer">Öffnen →</a>
    <button type="button" class="copy" on:click={copy} aria-label="Link kopieren">
      {copied ? '✓' : 'Kopieren'}
    </button>
    {#if looseMatch}<span class="badge warn">~match</span>{/if}
  {:else if result.status === 'not_found'}
    <span class="status muted">nicht gefunden</span>
  {:else}
    <span class="status err">Fehler</span>
  {/if}
</div>

<style>
  .row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
  }
  .row:last-child { border-bottom: none; }
  .name { flex: 1; font-weight: 600; }
  .badge {
    display: inline-block;
    font-size: 0.75rem;
    border-radius: 4px;
    padding: 0.1rem 0.4rem;
    margin-left: 0.3rem;
  }
  .badge.source { background: var(--accent); color: var(--bg); }
  .badge.warn { background: var(--warning); color: var(--bg); }
  .link {
    color: var(--accent);
    text-decoration: none;
  }
  .link:hover { text-decoration: underline; }
  .copy {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 4px;
    padding: 0.15rem 0.5rem;
    cursor: pointer;
    font-size: 0.8rem;
  }
  .copy:hover { background: var(--bg-surface); }
  .status.muted { color: var(--text-muted); }
  .status.err { color: var(--error); }
</style>
```

- [ ] **Step 4: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/components/ServiceItem.test.ts`
Expected: 5 Tests PASS.

- [ ] **Step 5: `ServiceList.svelte` implementieren**

`frontend/src/lib/components/ServiceList.svelte`:

```svelte
<script lang="ts">
  import ServiceItem from './ServiceItem.svelte';
  import { services } from '$lib/stores/services';

  export let sourceService: string;
  export let sourceUrl: string;
  export let targets: Record<string, { status: 'ok' | 'not_found' | 'error'; url?: string; confidence?: number }>;

  function displayName(id: string): string {
    return $services[id]?.name ?? id;
  }

  $: targetIds = Object.keys(targets).filter((id) => id !== sourceService);
</script>

<div class="list">
  <ServiceItem
    serviceId={sourceService}
    displayName={displayName(sourceService)}
    result={{ status: 'ok', url: sourceUrl, confidence: 1.0 }}
    isSource
  />
  {#each targetIds as id (id)}
    <ServiceItem serviceId={id} displayName={displayName(id)} result={targets[id]} />
  {/each}
</div>

<style>
  .list { display: flex; flex-direction: column; }
</style>
```

- [ ] **Step 6: `Skeleton.svelte` implementieren**

`frontend/src/lib/components/Skeleton.svelte`:

```svelte
<div class="skel">
  <div class="cover" />
  <div class="lines">
    <div class="line" style="width: 70%" />
    <div class="line" style="width: 40%" />
    <div class="line" style="width: 80%" />
    <div class="line" style="width: 80%" />
    <div class="line" style="width: 80%" />
  </div>
</div>

<style>
  .skel {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .cover {
    width: 130px;
    height: 130px;
    background: var(--bg-surface);
    border-radius: 6px;
    animation: pulse 1.5s ease-in-out infinite;
  }
  .lines { flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }
  .line {
    height: 1rem;
    background: var(--bg-surface);
    border-radius: 4px;
    animation: pulse 1.5s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
  }
  @media (max-width: 639px) {
    .skel { flex-direction: column; align-items: center; }
    .cover { width: 100%; max-width: 220px; height: 220px; }
  }
</style>
```

- [ ] **Step 7: `ResultCard.svelte` implementieren**

`frontend/src/lib/components/ResultCard.svelte`:

```svelte
<script lang="ts">
  import ServiceList from './ServiceList.svelte';
  import type { ConvertResponse } from '$lib/api/types';

  export let result: ConvertResponse;
</script>

<article class="card">
  <div class="cover-wrap">
    {#if result.source.coverUrl}
      <img class="cover" src={result.source.coverUrl} alt="Cover: {result.source.title ?? ''}" />
    {:else}
      <div class="cover cover--missing" aria-hidden="true"></div>
    {/if}
  </div>
  <div class="meta">
    <h2 class="title">{result.source.title ?? 'Unbekannter Titel'}</h2>
    {#if result.source.artists?.length}
      <p class="artists">{result.source.artists.join(', ')}</p>
    {/if}
    <ServiceList
      sourceService={result.source.service}
      sourceUrl={result.source.url}
      targets={result.targets ?? {}}
    />
    <slot name="share" />
  </div>
</article>

<style>
  .card {
    display: flex;
    gap: 1.25rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--bg-surface);
  }
  .cover-wrap { flex: 0 0 auto; }
  .cover {
    width: 130px;
    height: 130px;
    object-fit: cover;
    border-radius: 6px;
    background: var(--bg);
  }
  .cover--missing { background: var(--bg); }
  .meta { flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }
  .title { margin: 0; font-size: 1.25rem; }
  .artists { margin: 0; color: var(--text-muted); }
  @media (max-width: 639px) {
    .card { flex-direction: column; align-items: center; text-align: center; }
    .cover { width: 100%; max-width: 220px; height: 220px; }
    .meta { width: 100%; text-align: left; }
  }
</style>
```

- [ ] **Step 8: Suite laufen lassen**

Run: `cd frontend && pnpm test`
Expected: alle Tests PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/components/ResultCard.svelte \
        frontend/src/lib/components/ServiceList.svelte \
        frontend/src/lib/components/ServiceItem.svelte frontend/src/lib/components/ServiceItem.test.ts \
        frontend/src/lib/components/Skeleton.svelte
git commit -m "feat(frontend): ResultCard layout with ServiceList, ServiceItem, Skeleton"
```

---

## Task 7: ErrorPanel + +page.svelte (Wiring, ?url=, AbortController)

**Ziel:** `ErrorPanel` zeigt deutschsprachige Meldung + Copy-Debug-Button (Format B). `+page.svelte` verdrahtet InputBar, HistoryDropdown, Skeleton, ResultCard, ErrorPanel. Unterstützt `?url=`-Autoload und bricht laufende Requests via AbortController ab.

**Files:**
- Create: `frontend/src/lib/components/ErrorPanel.svelte`
- Create: `frontend/src/lib/components/ErrorPanel.test.ts`
- Modify: `frontend/src/routes/+page.svelte`

- [ ] **Step 1: Failing Test für `ErrorPanel` schreiben**

`frontend/src/lib/components/ErrorPanel.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import ErrorPanel from './ErrorPanel.svelte';
import { ApiError } from '$lib/api/types';

describe('ErrorPanel', () => {
  it('renders friendly message for invalid_url', () => {
    const err = new ApiError('invalid_url', 400, 'bad', 'https://x');
    const { getByText } = render(ErrorPanel, { props: { error: err } });
    expect(getByText(/ungültiger link/i)).toBeInTheDocument();
  });

  it('renders offline message', () => {
    const err = new ApiError('offline', 0, 'net', 'https://x');
    const { getByText } = render(ErrorPanel, { props: { error: err } });
    expect(getByText(/keine verbindung/i)).toBeInTheDocument();
  });

  it('copy-debug writes format-B string to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const err = new ApiError('invalid_url', 400, 'bad url', 'https://x');
    const { getByRole } = render(ErrorPanel, { props: { error: err } });
    await fireEvent.click(getByRole('button', { name: /debug.*kopieren/i }));
    expect(writeText).toHaveBeenCalledTimes(1);
    const text = writeText.mock.calls[0][0] as string;
    expect(text).toMatch(/^invalid_url: bad url/);
    expect(text).toContain('URL: https://x');
    expect(text).toMatch(/Zeit: \d{4}-\d{2}-\d{2}T/);
  });
});
```

- [ ] **Step 2: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/components/ErrorPanel.test.ts`
Expected: FAIL.

- [ ] **Step 3: `ErrorPanel.svelte` implementieren**

`frontend/src/lib/components/ErrorPanel.svelte`:

```svelte
<script lang="ts">
  import { ApiError, type ApiErrorCode } from '$lib/api/types';

  export let error: ApiError;

  const messages: Record<ApiErrorCode, string> = {
    invalid_url: 'Ungültiger Link.',
    unsupported_service: 'Dieser Dienst wird nicht unterstützt.',
    not_found: 'Kurzlink nicht gefunden.',
    rate_limited: "Zu viele Anfragen — versuch's in einer Minute erneut.",
    server_error: "Server-Fehler. Versuch's gleich nochmal.",
    offline: 'Keine Verbindung zum Server.'
  };

  let copied = false;

  async function copyDebug() {
    const ts = new Date().toISOString();
    const text =
      `${error.code}: ${error.message}\n` +
      `URL: ${error.sourceUrl ?? '-'}\n` +
      `Zeit: ${ts}`;
    await navigator.clipboard.writeText(text);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }
</script>

<section class="panel" role="alert">
  <h3>{messages[error.code]}</h3>
  {#if error.status === 400 && error.message && error.message !== messages[error.code]}
    <p class="detail">{error.message}</p>
  {/if}
  <button type="button" class="debug" on:click={copyDebug}>
    {copied ? 'Kopiert ✓' : 'Debug-Info kopieren'}
  </button>
</section>

<style>
  .panel {
    padding: 1rem;
    border: 1px solid var(--error);
    border-radius: 8px;
    background: color-mix(in srgb, var(--error) 12%, var(--bg));
  }
  h3 { margin: 0 0 0.5rem 0; color: var(--error); }
  .detail { margin: 0 0 0.75rem 0; color: var(--text-muted); }
  .debug {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 4px;
    padding: 0.3rem 0.6rem;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .debug:hover { background: var(--bg-surface); }
</style>
```

- [ ] **Step 4: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/components/ErrorPanel.test.ts`
Expected: 3 Tests PASS.

- [ ] **Step 5: `+page.svelte` mit voller Verdrahtung**

`frontend/src/routes/+page.svelte` ersetzen:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import InputBar from '$lib/components/InputBar.svelte';
  import HistoryDropdown from '$lib/components/HistoryDropdown.svelte';
  import ResultCard from '$lib/components/ResultCard.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import ErrorPanel from '$lib/components/ErrorPanel.svelte';
  import ShareButton from '$lib/components/ShareButton.svelte';
  import { convert, ApiError } from '$lib/api/client';
  import { addHistory } from '$lib/stores/history';
  import type { ConvertResponse } from '$lib/api/types';

  let inputValue = '';
  let dropdownOpen = false;
  let loading = false;
  let result: ConvertResponse | null = null;
  let error: ApiError | null = null;
  let currentController: AbortController | null = null;

  async function runConvert(url: string) {
    currentController?.abort();
    const ctrl = new AbortController();
    currentController = ctrl;
    loading = true;
    error = null;
    result = null;
    inputValue = url;
    try {
      const res = await convert(url, { signal: ctrl.signal });
      if (ctrl.signal.aborted) return;
      result = res;
      addHistory({
        sourceUrl: url,
        title: res.source.title ?? url,
        artists: res.source.artists ?? [],
        coverUrl: res.source.coverUrl ?? null,
        timestamp: Date.now()
      });
    } catch (e) {
      if (ctrl.signal.aborted || (e as DOMException).name === 'AbortError') return;
      error = e instanceof ApiError ? e : new ApiError('server_error', 0, String(e), url);
    } finally {
      if (currentController === ctrl) {
        loading = false;
        currentController = null;
      }
    }
  }

  onMount(() => {
    const urlParam = $page.url.searchParams.get('url');
    if (urlParam) runConvert(urlParam);
  });
</script>

<div class="home">
  <div class="input-wrap">
    <InputBar
      bind:value={inputValue}
      disabled={loading}
      on:submit={(e) => runConvert(e.detail.url)}
      on:focus={() => (dropdownOpen = true)}
      on:blur={() => (dropdownOpen = false)}
    />
    <HistoryDropdown
      open={dropdownOpen}
      on:select={(e) => { dropdownOpen = false; runConvert(e.detail.url); }}
    />
  </div>

  {#if loading}
    <Skeleton />
  {:else if error}
    <ErrorPanel {error} />
  {:else if result}
    <ResultCard {result}>
      <svelte:fragment slot="share">
        <ShareButton sourceUrl={result.source.url} />
      </svelte:fragment>
    </ResultCard>
  {/if}
</div>

<style>
  .home { display: flex; flex-direction: column; gap: 1.5rem; }
  .input-wrap { position: relative; }
</style>
```

- [ ] **Step 6: `ShareButton` temporär als Stub anlegen, damit die Page kompiliert**

`frontend/src/lib/components/ShareButton.svelte`:

```svelte
<script lang="ts">
  export let sourceUrl: string;
</script>

<div data-share={sourceUrl}></div>
```

(wird in Task 8 vollständig implementiert.)

- [ ] **Step 7: Dev-Server smoke-testen**

Run (interaktiv): `cd frontend && pnpm dev`
Erwartet: `/` rendert mit Header, Input; `http://localhost:5173/?url=https://tidal.com/track/1566` feuert einen Convert-Call (Backend muss auf `:8080` laufen; falls nicht, zeigt sich der „Keine Verbindung zum Server"-Error — das ist auch okay als Smoke-Check).

Stop mit Ctrl-C.

- [ ] **Step 8: Tests laufen lassen**

Run: `cd frontend && pnpm test`
Expected: alle PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/components/ErrorPanel.svelte frontend/src/lib/components/ErrorPanel.test.ts \
        frontend/src/lib/components/ShareButton.svelte \
        frontend/src/routes/+page.svelte
git commit -m "feat(frontend): wire home page with ?url= autoload and AbortController"
```

---

## Task 8: ShareButton + /c/[shortId]-Route

**Ziel:** `ShareButton` ruft beim Klick einen zweiten `convert`-Call mit `share=true` auf, zeigt danach `https://…/c/<id>` + Copy-Button. `/c/[shortId]`-Route lädt via `lookup` und zeigt dasselbe Result-Layout.

**Files:**
- Modify: `frontend/src/lib/components/ShareButton.svelte`
- Create: `frontend/src/lib/components/ShareButton.test.ts`
- Create: `frontend/src/routes/c/[shortId]/+page.svelte`

- [ ] **Step 1: Failing Test für `ShareButton`**

`frontend/src/lib/components/ShareButton.test.ts`:

```ts
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import ShareButton from './ShareButton.svelte';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('ShareButton', () => {
  it('initially shows Teilen button', () => {
    const { getByRole } = render(ShareButton, { props: { sourceUrl: 'https://x' } });
    expect(getByRole('button', { name: /teilen/i })).toBeInTheDocument();
  });

  it('fetches share-id on click and displays short link', async () => {
    server.use(
      http.get('*/api/v1/convert', ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('share')).toBe('true');
        return HttpResponse.json({ source: { service: 'spotify' }, targets: {}, share: { id: 'ab3x9k' } });
      })
    );
    const { getByRole, getByText } = render(ShareButton, { props: { sourceUrl: 'https://x' } });
    await fireEvent.click(getByRole('button', { name: /teilen/i }));
    await waitFor(() => expect(getByText(/ab3x9k/)).toBeInTheDocument());
  });

  it('shows error state on share-fail', async () => {
    server.use(
      http.get('*/api/v1/convert', () =>
        HttpResponse.json({ code: 'server_error', message: 'boom' }, { status: 500 })
      )
    );
    const { getByRole, getByText } = render(ShareButton, { props: { sourceUrl: 'https://x' } });
    await fireEvent.click(getByRole('button', { name: /teilen/i }));
    await waitFor(() => expect(getByText(/fehler/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Test laufen lassen — erwartet FAIL**

Run: `cd frontend && pnpm test src/lib/components/ShareButton.test.ts`
Expected: FAIL.

- [ ] **Step 3: `ShareButton.svelte` voll implementieren**

`frontend/src/lib/components/ShareButton.svelte` überschreiben:

```svelte
<script lang="ts">
  import { convert, ApiError } from '$lib/api/client';

  export let sourceUrl: string;

  let state: 'idle' | 'loading' | 'done' | 'error' = 'idle';
  let shortUrl: string | null = null;
  let copied = false;

  async function share() {
    state = 'loading';
    try {
      const res = await convert(sourceUrl, { share: true });
      const id = (res as { share?: { id: string } }).share?.id;
      if (!id) throw new ApiError('server_error', 200, 'no share id', sourceUrl);
      shortUrl = `${window.location.origin}/c/${id}`;
      state = 'done';
    } catch {
      state = 'error';
    }
  }

  async function copy() {
    if (!shortUrl) return;
    await navigator.clipboard.writeText(shortUrl);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }
</script>

<div class="share">
  {#if state === 'idle' || state === 'loading'}
    <button type="button" on:click={share} disabled={state === 'loading'}>
      {state === 'loading' ? 'Erzeuge Link …' : 'Teilen'}
    </button>
  {:else if state === 'done' && shortUrl}
    <code>{shortUrl}</code>
    <button type="button" class="copy" on:click={copy}>
      {copied ? '✓' : 'Kopieren'}
    </button>
  {:else}
    <span class="err">Fehler beim Erzeugen des Links</span>
    <button type="button" on:click={share}>Nochmal</button>
  {/if}
</div>

<style>
  .share { display: flex; gap: 0.5rem; align-items: center; margin-top: 0.75rem; }
  button {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 4px;
    padding: 0.3rem 0.75rem;
    cursor: pointer;
  }
  button:hover { background: var(--bg-surface); }
  .copy { font-size: 0.85rem; }
  code {
    background: var(--bg-surface);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }
  .err { color: var(--error); }
</style>
```

- [ ] **Step 4: Test laufen lassen — erwartet PASS**

Run: `cd frontend && pnpm test src/lib/components/ShareButton.test.ts`
Expected: 3 Tests PASS.

- [ ] **Step 5: `/c/[shortId]`-Route implementieren**

`frontend/src/routes/c/[shortId]/+page.svelte`:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import ResultCard from '$lib/components/ResultCard.svelte';
  import Skeleton from '$lib/components/Skeleton.svelte';
  import ErrorPanel from '$lib/components/ErrorPanel.svelte';
  import { lookup, ApiError } from '$lib/api/client';
  import type { ConvertResponse } from '$lib/api/types';

  let loading = true;
  let result: ConvertResponse | null = null;
  let error: ApiError | null = null;

  onMount(async () => {
    const shortId = $page.params.shortId;
    try {
      result = await lookup(shortId);
    } catch (e) {
      error = e instanceof ApiError ? e : new ApiError('server_error', 0, String(e));
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <Skeleton />
{:else if error}
  <ErrorPanel {error} />
{:else if result}
  <ResultCard {result} />
{/if}
```

- [ ] **Step 6: Suite laufen lassen**

Run: `cd frontend && pnpm test`
Expected: alle PASS.

- [ ] **Step 7: Build smoke**

Run: `cd frontend && pnpm build`
Expected: `build/index.html` + statische Assets generiert, kein Compile-Fehler.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/components/ShareButton.svelte frontend/src/lib/components/ShareButton.test.ts \
        frontend/src/routes/c/
git commit -m "feat(frontend): on-demand ShareButton and /c/[shortId] lookup route"
```

---

## Task 9: Dockerfile + Nginx-Config + Favicon

**Ziel:** Multi-stage Dockerfile baut Frontend und kopiert nach `nginx:1.27-alpine`. `nginx.conf` macht SPA-Fallback und cached Assets 1 Jahr immutable, HTML no-cache. Favicon als minimaler Lavender-Punkt.

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `frontend/.dockerignore`
- Create: `frontend/static/favicon.svg`

- [ ] **Step 1: `frontend/Dockerfile` schreiben**

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 2: `frontend/nginx.conf` schreiben**

```nginx
server {
  listen 80 default_server;
  server_name _;
  root /usr/share/nginx/html;

  gzip on;
  gzip_vary on;
  gzip_types text/css application/javascript image/svg+xml application/json;

  location ~* \.(js|css|woff2?|png|svg|jpg|ico)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    try_files $uri =404;
  }

  location / {
    try_files $uri $uri/ /index.html;
    add_header Cache-Control "no-cache";
  }
}
```

- [ ] **Step 3: `frontend/.dockerignore` schreiben**

```
node_modules
.svelte-kit
build
tests
.git
.github
*.md
```

- [ ] **Step 4: Minimales `frontend/static/favicon.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <circle cx="16" cy="16" r="12" fill="#b4befe" />
</svg>
```

- [ ] **Step 5: Image bauen**

Setup: `schema.d.ts` muss committed oder vorab erzeugt sein. Falls `backend/openapi.json` fehlt (CI-Artefakt), für den lokalen Build-Test vorab erzeugen:
```bash
cd backend && python -c "from linkhop.main import app; import json; json.dump(app.openapi(), open('openapi.json', 'w'))"
cd ../frontend && pnpm gen:api
```

Run:
```bash
cd frontend && docker build -t linkhop-frontend:dev .
```
Expected: Build erfolgreich, letzte Zeile `Successfully tagged linkhop-frontend:dev`.

- [ ] **Step 6: Container smoke-testen**

```bash
docker run --rm -d -p 8081:80 --name linkhop-fe-smoke linkhop-frontend:dev
curl -sf http://localhost:8081/ > /dev/null && echo OK
curl -sf http://localhost:8081/c/nonexistent > /dev/null && echo "SPA-fallback OK"
docker stop linkhop-fe-smoke
```
Expected: zwei `OK`-Ausgaben. Der zweite Aufruf muss `index.html` zurückgeben (Statuscode 200 via try_files).

- [ ] **Step 7: Commit**

```bash
git add frontend/Dockerfile frontend/nginx.conf frontend/.dockerignore frontend/static/favicon.svg
git commit -m "feat(frontend): Docker image with Nginx SPA-fallback and asset caching"
```

---

## Task 10: Playwright E2E + axe-core + GitHub Actions

**Ziel:** Playwright-Smoke-Tests (Happy-Path, Theme-Persistenz, Share-Flow, Error-Copy, History-Persistenz) inkl. `@axe-core/playwright`-A11y-Sanity-Check gegen docker-compose. GitHub-Actions-Workflow mit PR-Check (install/gen:api/drift/test/build), E2E-Job gegen Compose und Tag-Release-Image-Push.

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/tests/e2e/smoke.spec.ts`
- Modify: `frontend/package.json` (E2E-Script, Deps)
- Create: `.github/workflows/frontend.yml`
- Modify: `docker-compose.yml` (falls vorhanden — Frontend-Service ergänzen) oder Create

- [ ] **Step 1: Dependencies hinzufügen**

Run:
```bash
cd frontend
pnpm add -D @playwright/test @axe-core/playwright
pnpm exec playwright install chromium
```

- [ ] **Step 2: Scripts in `package.json` ergänzen**

Im `scripts`-Block:
```json
{
  "test:e2e": "playwright test",
  "test:e2e:ui": "playwright test --ui"
}
```

- [ ] **Step 3: `frontend/playwright.config.ts` schreiben**

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure'
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } }
  ]
});
```

Hinweis: `E2E_BASE_URL` zeigt auf den **Ingress**, wo Frontend (`/`) und Backend (`/api`) am selben Host liegen. In der lokalen docker-compose ist das typischerweise Traefik oder ein einfacher Nginx-Reverse-Proxy auf `:8080`. Falls die Compose-Datei nur Backend bedient, zeigt `E2E_BASE_URL` auf `http://localhost:5173` (Vite-Dev) mit Proxy.

- [ ] **Step 4: `frontend/tests/e2e/smoke.spec.ts` schreiben**

```ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const TEST_URL = process.env.E2E_TEST_URL ?? 'https://tidal.com/track/1566';

test.describe('linkhop smoke', () => {
  test('home renders and theme toggle persists', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('textbox', { name: /streaming-link/i })).toBeVisible();

    const toggle = page.getByRole('button', { name: /theme/i });
    await toggle.click();
    const themeAfterClick = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    await page.reload();
    const themeAfterReload = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );
    expect(themeAfterReload).toBe(themeAfterClick);
  });

  test('happy-path convert shows result', async ({ page }) => {
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({ timeout: 30_000 });
  });

  test('invalid url shows ErrorPanel with copy-debug', async ({ page }) => {
    await page.goto('/?url=https://not-a-music-service.example/xyz');
    await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('button', { name: /debug.*kopieren/i })).toBeVisible();
  });

  test('history persists across reload', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({ timeout: 30_000 });

    await page.goto('/');
    await page.getByRole('textbox', { name: /streaming-link/i }).focus();
    await expect(page.getByRole('listbox', { name: /verlauf/i })).toBeVisible();
  });

  test('share-button creates short-link that loads', async ({ page }) => {
    await page.goto(`/?url=${encodeURIComponent(TEST_URL)}`);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({ timeout: 30_000 });

    await page.getByRole('button', { name: /teilen/i }).click();
    const shortCode = page.locator('code').first();
    await expect(shortCode).toBeVisible({ timeout: 15_000 });
    const shortUrl = (await shortCode.textContent())!;
    const shortPath = new URL(shortUrl).pathname;

    await page.goto(shortPath);
    await expect(page.getByRole('link', { name: /öffnen/i }).first()).toBeVisible({ timeout: 15_000 });
  });

  test('a11y: no critical/serious violations on home', async ({ page }) => {
    await page.goto('/');
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();
    const blocking = results.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious');
    expect(blocking, JSON.stringify(blocking, null, 2)).toHaveLength(0);
  });
});
```

- [ ] **Step 5: Docker-Compose für E2E prüfen / ergänzen**

Falls im Repo-Root eine `docker-compose.yml` existiert, einen `frontend`-Service ergänzen (oder neu anlegen, falls nicht vorhanden):

```yaml
# docker-compose.yml (relevanter Ausschnitt)
services:
  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
  # + ein Reverse-Proxy (traefik oder nginx), der :8080 → /api → backend:8080, / → frontend:80 verteilt.
```

Falls kein Compose existiert, im ersten Lauf `E2E_BASE_URL=http://localhost:5173` und separat `pnpm dev` (FE) + Backend (`:8080`) starten. Vite-Proxy löst `/api` auf. Das reicht für E2E-Smoke.

- [ ] **Step 6: E2E lokal smoke-testen**

Voraussetzung: Backend + optional Redis/Postgres laufen auf `:8080`. Dann:

```bash
cd frontend
E2E_BASE_URL=http://localhost:5173 pnpm test:e2e -- --project=chromium --reporter=list
```

(Vite-Dev muss separat in anderem Shell laufen: `pnpm dev`.)

Expected: Happy-Path, Theme, Invalid-URL, History, Share, A11y — PASS. Bei flaky Network kann der 30s-Timeout für `convert` die Realität unterschätzen; dann auf 60s anheben.

- [ ] **Step 7: GitHub Actions `.github/workflows/frontend.yml` schreiben**

```yaml
name: frontend

on:
  pull_request:
    paths:
      - 'frontend/**'
      - 'backend/src/linkhop/**'
      - '.github/workflows/frontend.yml'
  push:
    branches: [main, master]
  release:
    types: [published]

jobs:
  check:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: frontend/.nvmrc
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml
      - uses: pnpm/action-setup@v3
        with:
          version: 9

      - name: Install deps
        run: pnpm install --frozen-lockfile

      - name: Export backend openapi.json
        working-directory: backend
        run: |
          pip install -e .
          python -c "from linkhop.main import app; import json; json.dump(app.openapi(), open('openapi.json','w'))"

      - name: Generate API schema
        run: pnpm gen:api

      - name: Check schema drift
        run: git diff --exit-code src/lib/api/schema.d.ts

      - name: Type check
        run: pnpm check

      - name: Unit + component tests
        run: pnpm test

      - name: Build
        run: pnpm build

  e2e:
    runs-on: ubuntu-latest
    needs: check
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: frontend/.nvmrc
          cache: pnpm
          cache-dependency-path: frontend/pnpm-lock.yaml
      - uses: pnpm/action-setup@v3
        with:
          version: 9
      - name: Install deps
        run: pnpm install --frozen-lockfile
      - name: Install Playwright browsers
        run: pnpm exec playwright install --with-deps chromium

      - name: Start backend stack
        working-directory: .
        run: docker compose up -d --wait

      - name: Start frontend dev server
        run: pnpm dev &
        env:
          CI: 'true'

      - name: Wait for frontend
        run: npx wait-on http://localhost:5173

      - name: Run E2E
        env:
          E2E_BASE_URL: http://localhost:5173
        run: pnpm test:e2e

      - name: Upload Playwright report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/playwright-report/

  image:
    runs-on: ubuntu-latest
    needs: check
    if: github.event_name == 'release'
    permissions:
      packages: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Export backend openapi.json
        run: |
          cd backend && pip install -e . && python -c "from linkhop.main import app; import json; json.dump(app.openapi(), open('openapi.json','w'))"
      - name: Generate schema for image build
        run: |
          cd frontend
          corepack enable
          pnpm install --frozen-lockfile
          pnpm gen:api
      - name: Build and push image
        uses: docker/build-push-action@v5
        with:
          context: frontend
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/linkhop-frontend:${{ github.event.release.tag_name }}
            ghcr.io/${{ github.repository_owner }}/linkhop-frontend:${{ github.sha }}
```

- [ ] **Step 8: Workflow-Sanity-Check (lokal via act oder einfach git-push-Review)**

Nach Commit und Push wird der PR-Workflow vom Checker gelaufen. Falls `docker compose up -d --wait` scheitert (keine Compose vorhanden), diesen Step entfernen und stattdessen Backend im Workflow direkt starten:

```yaml
- name: Start backend
  working-directory: backend
  run: |
    pip install -e .
    uvicorn linkhop.main:app --port 8080 &
    sleep 3
```

- [ ] **Step 9: Full-Suite lokal**

Run:
```bash
cd frontend && pnpm test && pnpm build
```
Expected: alles grün.

- [ ] **Step 10: Commit**

```bash
git add frontend/playwright.config.ts frontend/tests/e2e/ \
        frontend/package.json frontend/pnpm-lock.yaml \
        .github/workflows/frontend.yml
git commit -m "feat(frontend): Playwright E2E with axe-core and GitHub Actions CI"
```

---

## Abschluss

Nach Task 10 sollte:

- [ ] `pnpm test` grün (Unit + Component)
- [ ] `pnpm build` erzeugt `frontend/build/` ohne Fehler
- [ ] `docker build -t linkhop-frontend:dev frontend/` erfolgreich
- [ ] `pnpm test:e2e` gegen lokalen Stack grün
- [ ] `.github/workflows/frontend.yml` PR- und Release-Flows deckt

Offene Punkte aus der Spec, die nach V1-Ship zu entscheiden sind (keine Blocker):

- Logo-Redesign (aktuell: Lavender-Punkt-Favicon)
- Spotify-Test-URL im E2E, sobald Spotify-Dev-App eingerichtet ist
- Helm-Chart (Plan D)
