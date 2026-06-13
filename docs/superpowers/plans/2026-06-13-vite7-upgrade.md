# Vite-7-Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frontend von Vite 5 auf Vite 7 anheben und `esbuild` per pnpm-Override auf `>= 0.28.1` ziehen, um den Dependabot-Alert GHSA-gv7w-rqvm-qjhr zu schließen.

**Architecture:** Reines Build-Tooling-Upgrade im `frontend/`-Paket. `vite` 5→7 und `@sveltejs/vite-plugin-svelte` 4→6 werden gebumpt; ein versionsbeschränkter `pnpm.overrides`-Eintrag hebt verwundbare esbuild-Stände auf 0.28.1. SvelteKit, vitest, svelte und adapter-static bleiben unverändert (peer-Ranges decken Vite 7 bereits ab). Kein App-Code, kein Backend.

**Tech Stack:** Vite 7, @sveltejs/vite-plugin-svelte 6, esbuild 0.28.1, pnpm 10.33, Node 22.12+, SvelteKit 2.60 (adapter-static), Vitest 3.2.6.

**Spec:** `docs/superpowers/specs/2026-06-13-vite7-upgrade-design.md`

**Hinweise für alle Tasks:**
- Arbeitsverzeichnis für alle Kommandos: `frontend/`.
- Empirisch belegt: ein esbuild-0.28-Override unter Vite 5 bricht `pnpm build` (Destructuring-Transform gegen das alte Vite-5-Target). Dieser Plan funktioniert nur, weil Vite 7 ein moderneres Default-Target nutzt — **Task 1 Schritt 7 (`pnpm build`) ist das zentrale Gate**. Schlägt es fehl, ist das ein echter Blocker (Status BLOCKED, nicht umgehen): dann zurück zur Alert-Dismiss-Option eskalieren.
- Keine Versionen über die hier genannten hinaus anheben (kein SvelteKit-/vitest-/svelte-Bump).

---

### Task 1: Vite 7 + Svelte-Plugin 6 + esbuild-Override

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/.nvmrc`
- Modify (regeneriert): `frontend/pnpm-lock.yaml`

- [ ] **Step 1: Dependency-Versionen anheben**

In `frontend/package.json` im `devDependencies`-Block:
- `"vite": "^5.2.0"` → `"vite": "^7.3.0"`
- `"@sveltejs/vite-plugin-svelte": "^4.0.0"` → `"@sveltejs/vite-plugin-svelte": "^6.0.0"`

- [ ] **Step 2: esbuild-Override ergänzen**

In `frontend/package.json` einen Top-Level-Block einfügen (z. B. direkt vor `"devDependencies"`):

```json
  "pnpm": {
    "overrides": {
      "esbuild@<0.28.1": "^0.28.1"
    }
  },
```

Der versionsbeschränkte Key trifft nur verwundbare esbuild-Stände (`< 0.28.1`) und hebt sie auf die gepatchte Version.

- [ ] **Step 3: engines-Mindestversion anheben**

In `frontend/package.json` den `engines`-Block:

```json
  "engines": {
    "node": ">=22.12"
  },
```

(Vite 7 verlangt 22.12+; war vorher `>=22`.)

- [ ] **Step 4: .nvmrc pinnen**

`frontend/.nvmrc` von `22` auf:

```
22.12.0
```

- [ ] **Step 5: Installieren / Lockfile aktualisieren**

Run: `cd frontend && pnpm install`
Expected: läuft durch (eine Warnung „Ignored build scripts: esbuild@0.28.1, …" ist normal — esbuild liefert seine Binary über plattformspezifische optionalDependencies, kein Postinstall nötig). `frontend/pnpm-lock.yaml` wird aktualisiert.

- [ ] **Step 6: esbuild-Auflösung verifizieren**

Run: `cd frontend && pnpm why esbuild`
Expected: nur noch `esbuild@0.28.1` (kein `0.21.5` mehr), gezogen über `vite@7.x`.

Zusätzlich Vite-Version bestätigen:

Run: `cd frontend && pnpm exec vite --version`
Expected: `vite/7.x …`.

- [ ] **Step 7: Build — das zentrale Gate**

Run: `cd frontend && pnpm build`
Expected: `✓ built in …`, kein „Transforming destructuring … is not supported yet"-Fehler, `build/`-Verzeichnis entsteht. **Schlägt dieser Schritt fehl, STOP und Status BLOCKED melden** mit der vollständigen Fehlerausgabe — nicht weiterarbeiten.

- [ ] **Step 8: Typecheck**

Run: `cd frontend && pnpm check`
Expected: `svelte-check` ohne neue Fehler (0 errors). Vorbestehende Warnungen, die schon vor dem Upgrade da waren, sind okay.

- [ ] **Step 9: Unit-/Komponententests**

Run: `cd frontend && pnpm test`
Expected: `Test Files 11 passed (11)`, `Tests 61 passed (61)`.

- [ ] **Step 10: Commit**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/.nvmrc
git commit -m "build(frontend): upgrade to Vite 7, pin esbuild >= 0.28.1"
```

---

### Task 2: Dev-Server `?url=`-Smoke

**Files:** keine Änderungen — Verhaltensverifikation des `server.fs.strict: false`-Workarounds unter Vite 7.

Kontext: `frontend/vite.config.ts` setzt `server.fs.strict: false`, weil der Vite-5.4-Fix für CVE-2025-30208 Requests mit `://` im Query-String mit 403 blockt — genau der `?url=https://…`-Flow, der das Kern-Feature der App ist. Dieser Schritt prüft, dass Vite 7 den Pfad weiterhin durchlässt. Das Backend wird **nicht** gebraucht: getestet wird nur, dass der Dev-Server den `://`-Query nicht 403t (die Page rendert, der `/api`-Proxy ist separat).

- [ ] **Step 1: Dev-Server im Hintergrund starten**

```bash
cd frontend && nohup pnpm dev --host 127.0.0.1 > /tmp/vite7-dev.log 2>&1 < /dev/null &
disown
npx --yes wait-on -t 60000 http-get://127.0.0.1:5173 || { echo "::dev server kam nicht hoch::"; cat /tmp/vite7-dev.log; exit 1; }
```

Expected: `wait-on` kehrt erfolgreich zurück (Server lauscht auf 5173).

- [ ] **Step 2: `://`-Query darf nicht 403t**

```bash
curl -s -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:5173/?url=https://www.deezer.com/track/3135556'
```

Expected: `200` (nicht `403`). 403 bedeutet, der `fs.strict`-Workaround greift unter Vite 7 nicht mehr — dann Status DONE_WITH_CONCERNS und den Fund melden (vite.config bräuchte dann eine Vite-7-konforme Anpassung, z. B. `server.fs.allow`/aktualisierte Option).

- [ ] **Step 3: Dev-Server stoppen**

```bash
pkill -f "vite dev" || true
```

Expected: kein Fehler; der Hintergrundprozess endet.

- [ ] **Step 4: Kein Commit nötig** (reiner Verifikationsschritt; falls Schritt 2 einen Config-Fix erzwang, committet der den vite.config-Change separat mit Nachricht `fix(frontend): restore ://-query handling under Vite 7`).

---

### Task 3: Frontend-Docker-Image

**Files:**
- Modify: `frontend/Dockerfile:1` (Node-Tag pinnen)

Kontext: `frontend/Dockerfile` baut mit `node:22-alpine` + `pnpm install --frozen-lockfile` + `pnpm build`. `node:22-alpine` löst zur jeweils neuesten 22.x auf (heute > 22.12), erfüllt Vite 7 also — wird aber zur Reproduzierbarkeit auf 22.12 gepinnt, passend zu `.nvmrc`.

- [ ] **Step 1: Node-Tag pinnen**

In `frontend/Dockerfile` die erste Zeile:

```dockerfile
FROM node:22.12-alpine AS builder
```

(war `node:22-alpine`.)

- [ ] **Step 2: Image bauen**

Run: `cd frontend && docker build -t linkhop-frontend:vite7-smoke .`
Expected: Build läuft durch; `pnpm install --frozen-lockfile` akzeptiert das in Task 1 aktualisierte Lockfile (kein „lockfile out of date"), `pnpm build` erzeugt `build/`, finales nginx-Image entsteht. Schlägt `--frozen-lockfile` fehl, ist das Lockfile nicht konsistent mit package.json — zurück zu Task 1.

- [ ] **Step 3: Static-Serve-Smoke**

```bash
docker run -d --rm --name linkhop-fe-smoke -p 8088:80 linkhop-frontend:vite7-smoke
sleep 2
curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8088/
docker stop linkhop-fe-smoke
```

Expected: `200` (nginx serviert die gebaute `index.html`). Falls Port 8088 belegt ist, anderen freien Port wählen.

- [ ] **Step 4: Commit**

```bash
git add frontend/Dockerfile
git commit -m "build(frontend): pin Node 22.12 in image for Vite 7"
```

---

### Task 4: Abschluss-Verifikation

**Files:** keine Änderungen — reiner Verifikationslauf.

- [ ] **Step 1: Gesamtlauf der lokalen Gates**

```bash
cd frontend && pnpm check && pnpm test && pnpm build
```

Expected: check 0 errors, `Tests 61 passed (61)`, Build grün.

- [ ] **Step 2: Versionen final bestätigen**

```bash
cd frontend && pnpm exec vite --version && pnpm why esbuild | grep -m1 "esbuild@"
```

Expected: `vite/7.x` und `esbuild@0.28.1`.

- [ ] **Step 3: Sauberkeitscheck**

Run: `git status --short`
Expected: keine unbeabsichtigten Änderungen außerhalb der committeten `frontend/`-Dateien.

- [ ] **Step 4: Dependabot-Folgewirkung notieren**

Kein Code — festhalten (im Abschlussbericht an den Menschen): Der Alert GHSA-gv7w-rqvm-qjhr schließt sich automatisch, sobald der Branch mit `esbuild@0.28.1` im Lockfile nach `master` gemergt und gepusht ist. Nach dem Push den `frontend`-CI-Workflow (build + E2E inkl. `?url=https://…`-Smoke) beobachten — er deckt den `fs.strict`-Pfad gegen ein echtes Backend ab.
