# linkhop — Frontend-Design-Spezifikation (Plan C)

**Datum:** 2026-04-19
**Status:** Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (Brainstorming mit Claude)
**Referenz:** baut auf `docs/superpowers/specs/2026-04-18-linkhop-design.md` auf (V1-Design)

## Überblick

Das Frontend ist die Browser-UI von linkhop: ein User fügt einen Musik-Streaming-Link ein und bekommt die äquivalenten Links auf den aktiven Ziel-Diensten zurück. Die UI ist bewusst minimal (ein Input-Feld, ein Result-Block, Theme-Toggle) und konsumiert ausschließlich die öffentliche `/api/v1`-HTTP-API des Backends. Es gibt kein SSR und keinen Backend-for-Frontend-Layer — das Frontend ist eine statische Single-Page-Application.

Diese Spec fixiert die Design-Entscheidungen für die V1-Implementierung. Sie erweitert die V1-Design-Spec um die konkreten Technologie-, Component- und Flow-Entscheidungen, die während des Frontend-Brainstormings getroffen wurden.

## Scope

### In V1 (diese Spec)

- Konvertierungs-Input und Ergebnis-Darstellung (Track / Album / Artist)
- Theme-Toggle Catppuccin Mocha / Latte mit `auto`-Modus
- Short-Link-Share per `/c/[shortId]`-Route
- **History (A):** Die letzten ~20 Konvertierungen in `localStorage`; taucht als Auto-complete unter dem Input-Feld auf (Option C aus Brainstorming — kontextuell, unsichtbar, wenn nicht benötigt). Pro Eintrag werden **nur Preview-Daten** gespeichert (`sourceUrl`, `title`, `artists`, `coverUrl`, `timestamp`). Re-Klick auf einen Eintrag feuert einen frischen `convert`-Call — das Backend hat einen 7-Tage-Cache, Kosten sind vernachlässigbar, und der User sieht aktuelle Daten (neue Ziel-Dienste, korrigierte Resolves).
- **Fehler-Copy-Button (D):** Format B — `code + message + source-URL + ISO-timestamp`. Reproduzierbar ohne Privacy-Rauschen (kein UA, keine Request-ID).
- **/services-Fetch (E):** Einmal pro App-Lifecycle, Ergebnis wird als Map `service-id → display-name` in den Komponenten verwendet. Deaktivierte Dienste (Backend-Config) sind **komplett unsichtbar** — es gibt keinen "nicht verfügbar"-Indikator.
- **`?url=` Query-Param auf `/`:** Direkt-Link von außen (Bookmarks, Browser-Share-Targets) konvertiert automatisch beim Mount.

### Explizit nicht in V1

- Clipboard-Auto-Detect beim Laden der Seite
- Eigene "alle Links kopieren"-Aktion (pro-Dienst-Copy reicht)
- Eigene `/history`-Route (die Auto-complete unter dem Input deckt den Use-Case ab)
- I18n (UI ist monolingual Deutsch in V1)
- Web-Fonts (System-Font-Stack reicht, spart Round-Trips)

## Stack & Tooling (Approach 2 — Standard)

| Bereich | Wahl | Begründung |
|---|---|---|
| Framework | SvelteKit + TypeScript | Per V1-Spec vorgegeben; statisch build-bar, Component-Modell passt zur minimalen UI |
| Adapter | `@sveltejs/adapter-static` mit `fallback: "index.html"` | SPA-Fallback, weil `/c/[shortId]` dynamisch ist und nicht vor-gerendert werden kann |
| Package-Manager | pnpm | Standard-Wahl; Lockfile-Determinismus, wenig Noise |
| Build-Tool | Vite | SvelteKit-Default |
| Type-Generation | `openapi-typescript` | Generiert TS-Typen aus dem FastAPI-OpenAPI-Schema; Drift zwischen FE und BE wird zum CI-Fail, nicht zum Runtime-Bug |
| Unit-Tests | Vitest | Gleiche Toolchain wie Build |
| Component-Tests | `@testing-library/svelte` | Läuft im selben Vitest-Run |
| Mocking | MSW (Mock Service Worker) | Für Unit/Component-Tests |
| E2E | Playwright + `@axe-core/playwright` | Gegen docker-compose-Stack; axe-Sanity fängt Catppuccin-Kontrast-Regressionen |
| CSS | CSS Custom Properties, kein Framework | Catppuccin-Tokens selbst definieren; Tailwind/Shadcn ist Overkill für drei Screens |
| Prod-Server | Nginx Alpine (Container) | Static serving + SPA-fallback |

## Repository-Layout

Monorepo bleibt; neues Top-Level-Verzeichnis `frontend/` neben dem bestehenden `backend/`:

```
linkconverter/
├── backend/                       # bestehend
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api/               # TS-Client + generiertes OpenAPI-Schema (schema.d.ts committed)
│   │   │   ├── components/        # s. u.
│   │   │   ├── stores/            # theme, history
│   │   │   └── theme/             # tokens.css (Catppuccin)
│   │   ├── routes/
│   │   │   ├── +layout.svelte     # Header (Wort-Mark + Theme-Toggle), /services-load
│   │   │   ├── +page.svelte       # Home (Input, Result, History, ?url=-Autoload)
│   │   │   └── c/[shortId]/+page.svelte
│   │   └── app.html               # inkl. FOUC-Schutz-Script (s. Theme-Sektion)
│   ├── static/                    # favicon, logo
│   ├── tests/
│   │   └── e2e/                   # Playwright-Smoke
│   ├── Dockerfile                 # multi-stage: node builder → nginx:alpine
│   ├── nginx.conf                 # SPA-fallback, gzip, asset-caching
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── svelte.config.js           # adapter-static, fallback: index.html
│   └── vite.config.ts             # server.proxy: /api → http://localhost:8080
└── docs/
```

## Rendering-Modus

**SPA mit `fallback: "index.html"`** (nicht Prerender-alles, nicht SSR).

Zwei zwingende Gründe:
1. `/c/[shortId]` kann nicht vor-gerendert werden — die Short-IDs entstehen erst zur Laufzeit.
2. `?url=`-Autoload auf `/` soll Deep-Link-fähig sein — server-seitig kein Rendering nötig.

Der `adapter-static` mit SPA-Fallback erzeugt eine einzige `index.html`, die Nginx für alle unbekannten Pfade ausliefert. Svelte-Routing übernimmt dann client-seitig.

## Komponenten

Alle Svelte-Single-File-Components unter `src/lib/components/`. Jede Komponente ist fokussiert auf eine Verantwortlichkeit:

| Komponente | Verantwortung |
|---|---|
| `Header.svelte` | Wort-Mark `linkhop.` (lavender, immer) + `ThemeToggle` rechts |
| `ThemeToggle.svelte` | 3-Zustand-Button, zyklisch: `auto → dark → light → auto`; Icon-Wechsel (🌓 / 🌙 / ☀️); `aria-label` je Zustand |
| `InputBar.svelte` | URL-Textfeld + Convert-Button (innen rechts). Focus → öffnet `HistoryDropdown`. Dispatcht `submit`-Event mit URL. |
| `HistoryDropdown.svelte` | Liest aus `history`-Store, zeigt bis zu 20 Einträge mit Title + Artist + verkürzter URL. Klick auf Eintrag füllt Input und dispatcht `submit`. |
| `ResultCard.svelte` | Layout-Container. Desktop (Layout C): Cover 130 px links, Metadaten + `ServiceList` rechts. Mobile (< 640 px): Cover oben, Liste darunter (Layout B). |
| `ServiceList.svelte` | Rendert ein `ServiceItem` pro Ziel-Dienst aus der `targets`-Map der Response. Quell-Dienst erscheint mit `(Quelle)`-Markierung als erstes, nicht klickbar. |
| `ServiceItem.svelte` | Ein Dienst-Zeile: Dienst-Name (aus `/services`-Map), Badge (`~match` bei 0.4–0.7, `nicht gefunden` bei `not_found`, rote Markierung bei `error`), Open-Link und Copy-Button |
| `ShareButton.svelte` | Klick → zweiter `convert(url, {share:true})`-Call → zeigt `linkhop…/c/<id>` + Copy-Button. Vor dem ersten Klick ist nur ein "Teilen"-Button sichtbar. |
| `ErrorPanel.svelte` | Angezeigt bei Fehler. Zeigt User-freundliche Nachricht (Tabelle in Error-Handling-Sektion) + Copy-Debug-Button mit Format-B-String |
| `Skeleton.svelte` | Placeholder-Shapes für Loading-State (Cover + Zeilen) |

### Zustände (aus V1-Spec, hier detailliert)

- **Empty:** Nur `InputBar` zentriert, Hint-Text im Feld ("Spotify-, Deezer- oder Tidal-Link einfügen …"), kein Result-Block.
- **Loading:** `Skeleton` an Stelle des Result-Blocks, `InputBar` bleibt sichtbar und editierbar. Eine neue Submit-Aktion bricht die laufende Konvertierung via `AbortController` ab (`signal` wird dem `fetch`-Aufruf mitgegeben), sodass kein veraltetes Result mehr ins UI zurückläuft.
- **Result:** `ResultCard` mit Source + Services.
- **Error:** `ErrorPanel` statt `ResultCard`. `InputBar` bleibt editierbar.

## State Management

Drei Svelte-Stores unter `src/lib/stores/`. `currentResult` ist **kein Store**, sondern lokaler Component-State in `+page.svelte` — resettet sich natürlich bei Neu-Konvertierung.

### `theme`-Store (`stores/theme.ts`)

```ts
type Pref = 'auto' | 'dark' | 'light';
type Effective = 'dark' | 'light';
```

- Initial-Wert aus `localStorage['linkhop:theme']`, sonst `'auto'`.
- `derived` effective-Store resolvt `auto` live via `matchMedia('(prefers-color-scheme: dark)')` inkl. `addEventListener('change', …)` — System-Umschaltung während der Session wird reflektiert.
- Subscription setzt `document.documentElement.setAttribute('data-theme', effective)` und schreibt `pref` zurück in `localStorage`.

### `history`-Store (`stores/history.ts`)

```ts
interface HistoryEntry {
  sourceUrl: string;
  title: string;
  artists: string[];
  coverUrl: string | null;
  timestamp: number;  // Date.now()
}
```

- Initial-Wert aus `localStorage['linkhop:history']` (JSON-Parse, silent-catch bei korrupten Daten → leeres Array).
- `add(entry)`: dedupliziert auf `sourceUrl` (neuer Eintrag steht an Position 0, alter Eintrag wird entfernt), capped bei 20, persistiert.
- `clear()`: leert Array und `localStorage`. UI-seitig optional ein "Verlauf leeren"-Button im Dropdown-Footer, kann aber auch in V1 weggelassen werden (siehe offene Punkte).

### `services`-Store (`stores/services.ts`)

- Initial-Wert `{}`, wird in `+layout.svelte`'s `load` einmalig aus `GET /api/v1/services` gefüllt.
- Map `service-id → {name, capabilities[]}`. Kein Refresh-Mechanismus — Reload genügt.

## Data Flow & Routing

### Home (`/`)

```
User → pastet URL in InputBar → submit
  → api.convert(url) ──GET /api/v1/convert?url=…──▶ Backend
  → 200: currentResult = response;
           history.add({sourceUrl, title, artists, coverUrl, timestamp})
  → ResultCard rendert source + services
  → (User klickt Share)
  → api.convert(url, {share:true}) ──GET /api/v1/convert?url=…&share=true──▶ Backend
  → 200 mit share.id
  → ShareButton zeigt https://…/c/<id> + Copy
```

`?url=`-Autoload: im `+page.svelte` onMount, wenn `$page.url.searchParams.get('url')` vorhanden ist, wird der Wert in `InputBar` gesetzt und `submit` dispatcht. History-Eintrag wird genauso geschrieben, als hätte der User selbst getippt.

### Short-Link-Route (`/c/[shortId]`)

```
User öffnet /c/ab3x9k
  → c/[shortId]/+page.svelte onMount
  → api.lookup('ab3x9k') ──GET /api/v1/c/ab3x9k──▶ Backend
  → 200 (gleiches ConvertResponse-Schema)
  → gleiche ResultCard-Darstellung wie Home
  → URL-Bar bleibt bei /c/ab3x9k (keine Redirects)
  → KEIN history.add (Short-Link-Aufruf ist kein eigener Konvertierungs-Event)
```

### API-Client

Ein dünner Fetch-Wrapper unter `src/lib/api/client.ts`:

```ts
export async function convert(url: string, opts?: {share?: boolean, targets?: string[]}): Promise<ConvertResponse>
export async function lookup(shortId: string): Promise<ConvertResponse>
export async function services(): Promise<ServicesResponse>
```

Jede Funktion:
- Baut URL + Query-Params (URLSearchParams)
- Nutzt `fetch()`, wirft `ApiError` mit strukturierten Feldern bei `!ok`
- Bei Network-Exception: wirft `ApiError` mit `code: 'offline'`

## Theme-Handling

### CSS-Tokens

Semantische Tokens als Custom Properties in `src/lib/theme/tokens.css`, **nicht** Catppuccin-Rohfarben in Components:

```css
:root[data-theme="dark"] {
  --bg: #1e1e2e;           /* base */
  --bg-surface: #313244;   /* surface0 */
  --text: #cdd6f4;         /* text */
  --text-muted: #bac2de;   /* subtext1 */
  --accent: #b4befe;       /* lavender */
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
```

Komponenten nutzen nur `var(--…)`.

### FOUC-Schutz

Ein synchrones Inline-Script in `app.html`, **vor** jedem gerenderten Inhalt, setzt `data-theme`:

```html
<script>
(function(){
  var p=localStorage.getItem('linkhop:theme')||'auto';
  var d=p==='dark'||(p==='auto'&&matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme',d?'dark':'light');
})();
</script>
```

Ohne diesen Block flasht bei Dark-Mode-Usern kurz das Latte-Theme, bevor Svelte hydratet.

### Toggle-UX

Single-Button oben rechts, zyklisch `auto → dark → light → auto`. Icon-Wechsel:
- `auto`: 🌓
- `dark`: 🌙
- `light`: ☀️

`aria-label` passt sich pro Zustand an ("Theme: automatisch, zum Wechseln klicken" etc.).

## Error-Handling

Alle Fehler landen im `ErrorPanel`. Der Copy-Debug-Button schreibt Format B:

```
{code}: {message}
URL: {sourceUrl}
Zeit: {ISO-8601-Timestamp}
```

### User-freundliche Meldungen

| HTTP-Status / Trigger | Anzeige (DE) |
|---|---|
| Fetch-Exception / offline | „Keine Verbindung zum Server." |
| 400 `invalid_url` | „Ungültiger Link." |
| 400 `unsupported_service` | „Dieser Dienst wird nicht unterstützt." |
| 404 (nur `/c/<id>`) | „Kurzlink nicht gefunden." |
| 429 `rate_limited` | „Zu viele Anfragen — versuch's in einer Minute erneut." |
| 5xx | „Server-Fehler. Versuch's gleich nochmal." |

Backend `message`-Feld wird bei 400 als Untertitel angezeigt, wenn vorhanden. Der Copy-Button enthält immer das strukturelle Format unabhängig davon, was oben angezeigt wird.

## Testing

Drei Ebenen, parallel zum Backend-Stil (Unit → Integration → Live).

### 1. Vitest Unit (`src/**/*.test.ts`)
- `history`-Store: add/dedupe/cap-bei-20, clear, korrupte localStorage-Daten
- `theme`-Store: Resolve `auto` via gemocktem `matchMedia`, change-Listener-Propagation
- `api`-Client: Fehler-Mapping (400 → code-spezifisch, Network-Exception → `offline`)

### 2. Component-Tests via `@testing-library/svelte` (im selben Vitest-Run)
- `InputBar`: Submit feuert `convert`-Event; `?url=`-Autoload triggert mount-submit
- `HistoryDropdown`: Fokus öffnet Panel; Klick füllt Input und submittet
- `ServiceItem`: Alle `status`-Fälle (ok / ok+~match / not_found / error) rendern korrekt (Badges, Link-Enabled-State)
- `ThemeToggle`: Klick zyklet, setzt `data-theme`, schreibt localStorage
- `ErrorPanel`: Copy-Button schreibt Format-B-String in Clipboard (via `navigator.clipboard`-Mock)
- `ShareButton`: Klick triggert zweiten convert, zeigt `/c/<id>` nach 200

### 3. Playwright E2E Smoke (`tests/e2e/`)
Läuft gegen `docker compose up` (Backend + Redis + Postgres):
- Happy-Path: Paste bekannten Spotify- oder Tidal-Test-Link → Result mit ≥1 Target-Link
- Theme-Toggle persistiert über Reload
- Share-Button erzeugt Short-ID, direktes Öffnen von `/c/<id>` zeigt dasselbe Result
- Ungültige URL → `ErrorPanel` sichtbar, Copy-Debug liefert erwartetes Format
- History persistiert über Reload (Input-Fokus → Dropdown zeigt vorherigen Eintrag)
- **A11y-Sanity:** `@axe-core/playwright` prüft Home-Seite (leer + mit Result) auf WCAG-AA-Verletzungen. Catppuccin-Kontraste sind grenzwertig, besonders `--text-muted` auf `--bg` — ein automatischer Check fängt Regressionen früh.

### Mocking
Unit/Component-Tests mocken `fetch` via MSW. E2E-Tests nutzen **kein** Mocking — sie laufen gegen echte Backend-Container.

### Ausführung

- `pnpm test` — Vitest (Unit + Component). Schnell, läuft in jedem PR.
- `pnpm test:e2e` — Playwright gegen docker-compose. Läuft in eigenem CI-Job.

## Build & Deployment

### Dockerfile (`frontend/Dockerfile`)

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:1.27-alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

Der Build konsumiert das **vor-generierte** und **committete** `src/lib/api/schema.d.ts`. Kein Netzwerk-Zugriff auf das Backend zur Build-Zeit nötig.

### Nginx (`frontend/nginx.conf`)

Nur `/` wird bedient — `/api/*` routet Traefik im Ingress direkt an den Backend-Pod, der Frontend-Container kennt das gar nicht.

```nginx
server {
  listen 80 default_server;
  root /usr/share/nginx/html;
  gzip on; gzip_vary on;
  gzip_types text/css application/javascript image/svg+xml;

  location ~* \.(js|css|woff2?|png|svg|jpg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
  }
  location / {
    try_files $uri $uri/ /index.html;
    add_header Cache-Control "no-cache";
  }
}
```

Hash-basierte Asset-Namen (Vite-Default) rechtfertigen `immutable`-Caching; HTML bleibt uncached, damit Deployments sofort sichtbar sind.

### Schema-Drift-Absicherung

`src/lib/api/schema.d.ts` wird **committed**. Der npm-Script `gen:api` regeneriert gegen laufendes Backend (Dev) oder `backend/openapi.json` (CI, vom Backend-Job als Artifact exportiert). CI läuft `pnpm gen:api && git diff --exit-code src/lib/api/schema.d.ts` — dirty führt zum Build-Fail. Schema-Drift zwischen FE und BE wird so im PR sichtbar und nie stumm.

### Dev-Workflow

- `pnpm dev`: Vite auf `:5173`, `server.proxy` route `/api/*` an `http://localhost:8080`. Dev-URLs matchen also Prod-URLs (same-origin, kein CORS-Rauschen).
- `pnpm gen:api`: Regeneriert `schema.d.ts`. Wird vor `pnpm dev` und `pnpm build` automatisch ausgeführt — über die Standard-npm-Hooks `predev` und `prebuild` in `package.json`, kein manueller Schritt, kein Pre-Commit-Hook, kein Husky.
- Node-Version fixiert über `engines.node` in `package.json` (`">=22"`, passt zum Dockerfile) und `.nvmrc` (`22`) für lokale Devs, die `nvm` / `fnm` nutzen.

### GitHub Actions (`.github/workflows/frontend.yml`)

- **PR + main:**
  - `frontend-check`: install → `gen:api` → Drift-Check → `lint` → `test` → `build`
  - `frontend-e2e`: `docker compose up -d`, poll `/api/v1/health`, `pnpm test:e2e`
- **Tag-Release:**
  - `frontend-image`: build & push nach `ghcr.io/<user>/linkhop-frontend:v<tag>` und `:<sha>` (matcht den Backend-Workflow)

### Helm-Chart

Die V1-Design-Spec listet bereits `frontend-deployment.yaml`, `frontend-service.yaml` und `ingress.yaml`. Konkret für V1:

- `templates/frontend-deployment.yaml`: `image: ghcr.io/<user>/linkhop-frontend:{{ .Values.frontend.image.tag | default .Chart.AppVersion }}`
- `templates/frontend-service.yaml`: `port: 80`
- `templates/ingress.yaml` (aus V1-Spec): Traefik routed `/api → backend-svc:8080`, sonst → `frontend-svc:80`
- Probes: `tcpSocket: port: 80` (liveness + readiness) — Nginx-Alpine hat standardmäßig kein curl/wget, HTTP-Probes würden extra Setup verlangen

## Offene Punkte (vor Implementierung zu klären)

- **Logo/Favicon:** noch nicht designed. Für V1 kann ein einfacher Lavender-Punkt (passt zum `linkhop.`-Wort-Mark) als `favicon.svg` starten; Redesign später.
- **`history.clear()`-UI:** aktuell spec-seitig optional. Vorschlag: kleiner "Verlauf leeren"-Link im Dropdown-Footer, wenn >0 Einträge vorhanden. Falls V1 ohne ausgeliefert wird, in einer späteren Iteration nachziehen.
- **Playwright-Test-Links:** Die E2E-Tests brauchen stabile Beispiel-URLs. Nach Plan B wurde für Tidal `tidal.com/track/1566` als stabil verifiziert; Spotify-Test-Link steht noch aus (User hat keine Spotify-Dev-App mit Client-Credentials, siehe V1-Spec offene Punkte).
- **`@axe-core/playwright` Config:** Initial nur Severity `critical` + `serious` gate'n, `moderate`/`minor` warnen — sonst blockiert Kontrast-Feintuning die Merges.

## Future Work (nicht in V1)

- Playlist-Support (V1-Spec-Nicht-Ziel)
- i18n / englische Locale
- Sharing via Web Share API (`navigator.share`) — browser-nativ, kein Backend-Aufwand; aber sinnvoll erst, wenn Mobile stärker adressiert wird
- `/history` als eigene Route mit Suche/Filter (falls History-Nutzung sich als Use-Case zeigt)
- PWA-Manifest + Offline-Cache für History
