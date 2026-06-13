# Image-Tag-Format + Placeholder Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release-Workflows publishen Container-Images künftig als `:X.Y.Z` (ohne `v`-Präfix), passend zum Helm-`appVersion`-Default; der InputBar-Placeholder nennt YouTube Music.

**Architecture:** Zwei GitHub-Actions-`image`-Jobs (backend.yml, frontend.yml) bekommen je einen Step, der die Version aus dem Release-Tag ohne führendes `v` ableitet, und nutzen diese statt des rohen `tag_name` im Docker-Image-Tag. Plus eine Placeholder-Textänderung im Frontend. Keine Helm-, keine Backend-Änderung.

**Tech Stack:** GitHub Actions, Bash-Parameter-Expansion, SvelteKit/Svelte 5.

**Spec:** `docs/superpowers/specs/2026-06-13-image-tag-and-placeholder-fixes-design.md`

**Hinweise für alle Tasks:**
- Arbeitsverzeichnis: Repo-Root `linkconverter` (Workflows), `frontend/` (Placeholder + Tests).
- Der Tag-Fix lässt sich lokal nicht über einen echten Release-Event testen; verifiziert werden die Bash-Strip-Logik isoliert und die YAML-Gültigkeit. Der echte Effekt zeigt sich beim nächsten Release (`v0.2.1` → Image `:0.2.1`).
- Kein Test referenziert den Placeholder-String (geprüft) — es muss kein Frontend-Test angepasst werden.

---

### Task 1: Image-Tags ohne `v`-Präfix in beiden Release-Workflows

**Files:**
- Modify: `.github/workflows/backend.yml` (`image`-Job: nach „Lowercase owner", und Tag-Zeile)
- Modify: `.github/workflows/frontend.yml` (`image`-Job: nach „Lowercase owner", und Tag-Zeile)

- [ ] **Step 1: Strip-Logik isoliert verifizieren**

```bash
TAG=v0.2.1; echo "${TAG#v}"
TAG=0.2.1; echo "${TAG#v}"
```
Expected: `0.2.1` und `0.2.1` (führendes `v` wird entfernt, ein bereits versionsloser Tag bleibt unverändert).

- [ ] **Step 2: backend.yml — Version-Step ergänzen**

In `.github/workflows/backend.yml`, im `image`-Job direkt nach dem Step

```yaml
      - name: Lowercase owner
        run: echo "OWNER_LC=${GITHUB_REPOSITORY_OWNER,,}" >> "$GITHUB_ENV"
```

diesen Step einfügen:

```yaml

      - name: Derive image version (strip leading v)
        env:
          TAG_NAME: ${{ github.event.release.tag_name }}
        run: echo "VERSION=${TAG_NAME#v}" >> "$GITHUB_ENV"
```

- [ ] **Step 3: backend.yml — Tag-Zeile umstellen**

In `.github/workflows/backend.yml` die Zeile

```yaml
            ghcr.io/${{ env.OWNER_LC }}/linkhop-backend:${{ github.event.release.tag_name }}
```

ersetzen durch:

```yaml
            ghcr.io/${{ env.OWNER_LC }}/linkhop-backend:${{ env.VERSION }}
```

(Die `:latest`-Zeile bleibt unverändert.)

- [ ] **Step 4: frontend.yml — Version-Step ergänzen**

In `.github/workflows/frontend.yml`, im `image`-Job direkt nach dem Step

```yaml
      - name: Lowercase owner
        run: echo "OWNER_LC=${GITHUB_REPOSITORY_OWNER,,}" >> "$GITHUB_ENV"
```

diesen Step einfügen:

```yaml

      - name: Derive image version (strip leading v)
        env:
          TAG_NAME: ${{ github.event.release.tag_name }}
        run: echo "VERSION=${TAG_NAME#v}" >> "$GITHUB_ENV"
```

- [ ] **Step 5: frontend.yml — Tag-Zeile umstellen**

In `.github/workflows/frontend.yml` die Zeile

```yaml
            ghcr.io/${{ env.OWNER_LC }}/linkhop-frontend:${{ github.event.release.tag_name }}
```

ersetzen durch:

```yaml
            ghcr.io/${{ env.OWNER_LC }}/linkhop-frontend:${{ env.VERSION }}
```

(Die `:latest`-Zeile bleibt unverändert.)

- [ ] **Step 6: YAML-Gültigkeit prüfen**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/backend.yml')); yaml.safe_load(open('.github/workflows/frontend.yml')); print('yaml ok')"
```
Expected: `yaml ok`.

Zusätzlich bestätigen, dass kein roher `tag_name` mehr als Image-Tag dient:

```bash
grep -n "linkhop-backend:\${{ github.event.release.tag_name\|linkhop-frontend:\${{ github.event.release.tag_name" .github/workflows/*.yml
```
Expected: keine Treffer.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/backend.yml .github/workflows/frontend.yml
git commit -m "ci: tag release images without leading v (match Chart.appVersion)"
```

---

### Task 2: InputBar-Placeholder um YouTube Music ergänzen

**Files:**
- Modify: `frontend/src/lib/components/InputBar.svelte:39`

- [ ] **Step 1: Placeholder-Text ändern**

In `frontend/src/lib/components/InputBar.svelte` die Zeile

```svelte
    placeholder="Spotify-, Deezer- oder Tidal-Link einfügen …"
```

ersetzen durch:

```svelte
    placeholder="Spotify-, Deezer-, Tidal- oder YouTube-Music-Link einfügen …"
```

- [ ] **Step 2: Frontend-Tests laufen lassen**

Run: `cd frontend && pnpm test`
Expected: `Test Files 11 passed (11)`, `Tests 61 passed (61)` — unverändert grün (kein Test prüft den Placeholder).

- [ ] **Step 3: Build prüfen**

Run: `cd frontend && pnpm build`
Expected: `✓ built …`, kein Fehler.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/components/InputBar.svelte
git commit -m "feat(frontend): mention YouTube Music in input placeholder"
```

---

### Task 3: Abschluss-Verifikation

**Files:** keine Änderungen — reiner Verifikationslauf.

- [ ] **Step 1: Workflows final prüfen**

```bash
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/backend.yml','.github/workflows/frontend.yml']]; print('yaml ok')"
grep -n "env.VERSION" .github/workflows/backend.yml .github/workflows/frontend.yml
```
Expected: `yaml ok`; je ein `:${{ env.VERSION }}`-Treffer pro Workflow.

- [ ] **Step 2: Frontend final**

```bash
cd frontend && pnpm test && pnpm build
```
Expected: 61 Tests grün, Build grün.

- [ ] **Step 3: Sauberkeitscheck**

Run: `git status --short`
Expected: keine unbeabsichtigten Änderungen außerhalb der committeten Dateien.
