# Vite-7-Upgrade — Design-Spezifikation

**Datum:** 2026-06-13
**Status:** Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (brainstorming mit Claude)

## Überblick

Dependabot meldet eine High-Severity-Lücke in `esbuild < 0.28.1`
(GHSA-gv7w-rqvm-qjhr): das **Deno-Modul** von esbuild prüft Binary-Hashes
nicht. Das Frontend zieht `esbuild@0.21.5` transitiv über `vite@5.4.21`.

Die Lücke ist für dieses Projekt praktisch nicht ausnutzbar (Node/pnpm-Build
prüft Hashes; esbuild ist reine Build-Zeit-Abhängigkeit, nicht im
ausgelieferten statischen Frontend). Trotzdem soll der Alert geschlossen
werden — und ein direkter `esbuild`-Override auf 0.28.1 unter Vite 5 bricht
den Build empirisch (Destructuring-Transform gegen das alte Vite-5-Target).
Dieser Spec hebt deshalb Vite auf 7 an, sodass der nötige esbuild-Override
nur noch ein Minor-Sprung ist und mit dem moderneren Vite-7-Default-Target
zusammenpasst.

## Ziele und Nicht-Ziele

### Ziele

- **Dependabot-Alert GHSA-gv7w-rqvm-qjhr geschlossen**: `esbuild` im
  Lockfile auf `>= 0.28.1`
- **Vite 5 → 7** mit grünem Build, Tests und E2E
- **Minimale Breaking-Surface**: nur Vite + Svelte-Plugin anfassen

### Nicht-Ziele

- **Kein SvelteKit-/vitest-/svelte-Upgrade**: alle akzeptieren Vite 7 bereits
  per peer-Range — nicht ohne Anlass anfassen
- **Keine App-Refaktorierung**: nur Build-Tooling, kein Feature-Code
- **Kein Backend-Bezug** (das ist seit der uv-Migration getrennt)

## Entscheidungsgrundlage: Vite 7 statt 6

Beide Pfade fassen Vite + `@sveltejs/vite-plugin-svelte` an und brauchen
den esbuild-Override. Vite 7 wurde gewählt, weil:

- esbuild-Baseline `^0.27` (ab Vite 7.3) → Override 0.27 → 0.28.1 ist der
  kleinstmögliche Sprung (Vite 6: `^0.25`)
- aktuellste Baseline, hält am längsten frisch
- SvelteKit/vitest/svelte/adapter-static bleiben unverändert (peer-Ranges
  decken Vite 7 ab)

Preis: Node-Mindestanforderung 22.12+ (Vite 6 liefe noch mit 22.0).

## Versionskompatibilität (geprüft)

| Paket | jetzt | Ziel | Vite-7-peer |
|---|---|---|---|
| `vite` | `^5.2.0` (5.4.21) | `^7.3.0` | — |
| `@sveltejs/vite-plugin-svelte` | `^4.0.0` (4.0.4) | `^6.0.0` | `^6.3.0 \|\| ^7.0.0` ✓ |
| `@sveltejs/kit` | `^2.60.1` | unverändert | `^5 \|\| ^6 \|\| ^7 \|\| ^8` ✓ |
| `vitest` | `^3.2.6` | unverändert | `^5 \|\| ^6 \|\| ^7.0.0-0` ✓ |
| `@sveltejs/adapter-static` | `^3.0.0` | unverändert | nur `@sveltejs/kit` ✓ |
| `esbuild` (transitiv) | 0.21.5 | `^0.28.1` (override) | Vite 7.3 zieht `^0.27` |

## Änderungen im Einzelnen

### `frontend/package.json`

- `vite`: `^5.2.0` → `^7.3.0`
- `@sveltejs/vite-plugin-svelte`: `^4.0.0` → `^6.0.0`
- Neuer Abschnitt:

  ```json
  "pnpm": {
    "overrides": {
      "esbuild@<0.28.1": "^0.28.1"
    }
  }
  ```

  Der versionsbeschränkte Override-Key trifft nur verwundbare Stände und
  hebt sie auf die gepatchte Version; bereits-gepatchte bleiben unberührt.

### `frontend/.nvmrc`

`22` → `22.12.0` (Vite-7-Minimum). CI liest `.nvmrc` über
`actions/setup-node` mit `node-version-file`.

### Lockfile

`pnpm install` aktualisiert `frontend/pnpm-lock.yaml`; committen.

## Verifikation (jeder Schritt ein Gate)

1. `pnpm install` — Lockfile-Update; `pnpm why esbuild` zeigt `0.28.1`
2. `pnpm check` (svelte-check) — keine neuen Typfehler
3. `pnpm test` (Vitest) — 61 Tests grün
4. **`pnpm build`** — der zentrale De-Risk: hier brach der Override unter
   Vite 5; unter Vite 7 muss er durchlaufen
5. `pnpm preview` + manueller/automatischer Smoke auf `?url=https://…`,
   um den `server.fs.strict: false`-Workaround (gegen den Vite-5.4-CVE-Fix
   für `://`-Queries) unter Vite 7 zu prüfen — der `?url=`-Flow ist
   Kern-Feature der App
6. `pnpm exec vite --version` → `7.x`

## Risiken

| Risiko | Einschätzung / Mitigation |
|---|---|
| esbuild-0.28-Override bricht auch Vite-7-Build | Vite-7-Default-Target ist modern genug; Schritt 4 verifiziert. Falls rot: echter Blocker → zurück zur Alert-Dismiss-Option. |
| `server.fs.strict: false`-Workaround veraltet/unzureichend unter Vite 7 | Schritt 5 + der bestehende E2E-Smoke (`?url=https://www.deezer.com/…` durch den Vite-Proxy) prüfen den `://`-Query-Pfad gezielt. |
| Frontend-Docker-Image bricht | `frontend/Dockerfile` baut über `pnpm build` — durch Schritt 4 abgedeckt; Image-Build als Teil der Abschluss-Verifikation. |
| `vitePreprocess`-Import ändert sich in plugin-svelte 6 | Export ist unverändert (`@sveltejs/vite-plugin-svelte`); `svelte.config.js` bleibt. Schritt 2/3 fangen Regressionen. |

## Folgewirkung

Sobald `esbuild@0.28.1` im Lockfile steht, schließt sich der
Dependabot-Alert GHSA-gv7w-rqvm-qjhr beim nächsten Push automatisch.
