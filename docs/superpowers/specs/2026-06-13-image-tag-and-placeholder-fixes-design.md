# Image-Tag-Format + Placeholder — Design-Spezifikation

**Datum:** 2026-06-13
**Status:** Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (brainstorming mit Claude)

## Überblick

Zwei kleine Folge-Fixes nach dem v0.2.0-Release:

1. **Image-Tag-Format-Diskrepanz.** Die Release-Workflows taggen Container-Images
   mit dem vollen Git-Release-Tag (`:vX.Y.Z`, mit `v`), während die Helm-Templates
   bei leerem `image.tag` aus `.Chart.AppVersion` ableiten (`:X.Y.Z`, ohne `v`).
   Der Helm-Default zeigt damit auf einen Tag, der nicht existiert — das Flux-Deployment
   muss den Tag bisher explizit mit `v` pinnen. Das fiel beim v0.2.0-Rollout auf.
2. **Placeholder.** `InputBar.svelte` nennt im Eingabe-Placeholder nur „Spotify-,
   Deezer- oder Tidal-Link" — YouTube Music fehlt, obwohl es seit v0.2.0 unterstützt wird.

## Ziele und Nicht-Ziele

### Ziele

- Künftige Release-Images heißen `:X.Y.Z` (ohne `v`), konsistent mit
  `Chart.appVersion`, README und SemVer-Image-Konvention
- Der Helm-Default `image.tag: ""` → `Chart.appVersion` funktioniert ohne
  explizites Tag-Pinning
- Placeholder nennt alle vier unterstützten Dienste

### Nicht-Ziele

- **Kein rückwirkendes Re-Tagging** von `v0.2.0` (das existierende `:v0.2.0`-Image
  bleibt; der Fix wirkt ab dem nächsten Release)
- **Keine Änderung am Flux-Repo** (separat) — nur als Folgewirkung dokumentiert
- **Keine Helm-Template-Änderung** (der bestehende Default wird durch den
  Workflow-Fix korrekt)

## Entscheidungsgrundlage

| Ansatz | Bewertung |
|---|---|
| **Workflow strippt `v` (gewählt)** | Image-Tags `:X.Y.Z`, konventionell (SemVer), passt zu appVersion + README. Helm-Default greift danach. |
| Helm nutzt `v`-Präfix | `:v{{ .Chart.AppVersion }}` bricht die appVersion-Semantik; jeder Chart-Consumer müsste das `v` mitdenken. |
| Beide Tags publishen | Abwärtskompatibel, aber doppelte Tags dauerhaft zu pflegen. |

## Änderungen im Einzelnen

### `.github/workflows/backend.yml` (`image`-Job)

Nach dem bestehenden `Lowercase owner`-Step einen Step ergänzen, der die
Image-Version aus dem Release-Tag ohne führendes `v` ableitet:

```yaml
- name: Derive image version (strip leading v)
  env:
    TAG_NAME: ${{ github.event.release.tag_name }}
  run: echo "VERSION=${TAG_NAME#v}" >> "$GITHUB_ENV"
```

Die Tag-Liste der `docker/build-push-action` nutzt `${{ env.VERSION }}` statt
`${{ github.event.release.tag_name }}`:

```yaml
tags: |
  ghcr.io/${{ env.OWNER_LC }}/linkhop-backend:${{ env.VERSION }}
  ghcr.io/${{ env.OWNER_LC }}/linkhop-backend:latest
```

### `.github/workflows/frontend.yml` (`image`-Job)

Identische Änderung für `linkhop-frontend` (eigener Step + Tag-Zeile).

### `frontend/src/lib/components/InputBar.svelte`

Placeholder (Zeile 39) von

```
Spotify-, Deezer- oder Tidal-Link einfügen …
```

zu

```
Spotify-, Deezer-, Tidal- oder YouTube-Music-Link einfügen …
```

Falls ein Komponententest (`InputBar.test.ts` o. ä.) den Placeholder-String
prüft, wird die Erwartung mitgezogen.

## Verifikation

- `${TAG_NAME#v}`-Logik lokal: `TAG=v0.2.1; echo "${TAG#v}"` → `0.2.1` (und ein
  bereits versionsloser Tag bliebe unverändert)
- Workflow-YAML parst (`yaml.safe_load`)
- Frontend: `pnpm test` (61+ Tests grün, inkl. evtl. Placeholder-Test), `pnpm build`

## Folgewirkung (außerhalb dieses Specs)

Beim nächsten Release (`v0.2.1`) publishen die Workflows `:0.2.1` (ohne `v`).
Das Flux-Repo (`apps/linkhop/values.yaml`) kann dann `backend/frontend.image.tag`
auf `"0.2.1"` setzen oder leer lassen (`""`), womit der Helm-appVersion-Default
greift. Dieser Schritt gehört zum nächsten Rollout, nicht zu diesem Fix.
