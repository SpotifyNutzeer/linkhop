# linkhop — Design-Spezifikation

**Datum:** 2026-04-18
**Status:** V1-Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (brainstorming mit Claude)

## Überblick

`linkhop` ist ein Web-Dienst, der Musik-Links zwischen Streaming-Diensten konvertiert — ähnlich Odesli/song.link. Ein Nutzer fügt einen Link eines Dienstes ein und bekommt denselben Inhalt (Track, Album oder Artist) auf allen anderen unterstützten Diensten.

Das Projekt besteht aus:

1. **Backend** (FastAPI, Python) mit öffentlicher HTTP-API und Service-Adaptern
2. **Frontend** (SvelteKit, statisch) mit Catppuccin-Mocha/Latte-Theme und Theme-Toggle
3. **Cache** (Redis) für aufgelöste Links
4. **Datenbank** (Postgres, extern erwartet) für teilbare Short-IDs und API-Keys
5. **Helm-Chart** für Kubernetes-Deployment, generisch mit `existingSecret`-Pattern

## Ziele und Nicht-Ziele

### Ziele (V1)

- Bidirektionale Konvertierung zwischen **Spotify, Deezer, Tidal, YouTube Music**
- Unterstützte Inhalte: **Tracks, Alben, Artists** (keine Playlists)
- **Öffentliche HTTP-API** mit OpenAPI-Dokumentation unter `/api/v1`
- **Rate-Limiting** anonym/mit API-Key, konfigurierbar
- **Teilbare Short-Links** (`/c/<id>`), persistent in Postgres
- **UI** in Catppuccin Mocha (Default) und Latte, mit Auto-Detect via `prefers-color-scheme` und manuellem Toggle
- **Helm-Chart** generisch einsetzbar, getestet gegen RKE2 + Traefik + cert-manager + external-dns

### Nicht-Ziele (V1)

- **Keine Playlists** (Track-für-Track-Auflösung ist aufwändig und fehleranfällig)
- **Kein Amazon Music** (keine öffentliche Such-API, nur über fragile Workarounds möglich)
- **Kein Apple Music** (erfordert kostenpflichtigen Developer-Account — kann später nachgeliefert werden)
- **Kein User-System, keine Self-Service API-Keys, kein Admin-Panel** (siehe "Future Work" — V2)
- **Keine eigene Auth** (wenn V2, dann via bestehendes Authentik)

## Architektur

```
  Client ──HTTPS──▶  Traefik Ingress  ──▶  Frontend-Pod (Nginx + statisches SvelteKit)
                                      │                 │
                                      └──▶  Backend-Pod (FastAPI) ──▶  Redis (Cache)
                                                        │           └▶  Postgres (Short-IDs, API-Keys)
                                                        │
                                                        └──▶  Service-Adapter
                                                                ├─ Spotify Web API
                                                                ├─ Deezer Public API
                                                                ├─ Tidal OpenAPI
                                                                └─ ytmusicapi (YouTube Music)
```

### Komponenten

| Komponente | Technologie | Rolle |
|---|---|---|
| Frontend | SvelteKit + TypeScript, statisch gebaut, via Nginx | UI, Theme-Handling, ruft eigene API auf |
| Backend | FastAPI (Python 3.12), uvicorn | API, Resolver/Searcher/Scorer, Rate-Limiting |
| Cache | Redis 7 (Bitnami-Subchart, Standalone) | Aufgelöste Konvertierungen, TTL-basiert |
| DB | Postgres 16 (extern, via cloudnative-pg) | Short-IDs, API-Keys |
| Ingress | Traefik (konfigurierbar) | TLS, Routing |

### Aufteilung Frontend/Backend

Zwei separate Pods im Chart. Routing per Ingress:

- `/` → Frontend-Pod
- `/api/*` → Backend-Pod

Begründung: Frontend ist statisch und kann stark gecached werden; Backend hat eigene Lebenszyklen (Crashes, Rolling-Updates durch API-Adapter-Updates) — lose Kopplung erleichtert Ops.

## Unterstützte Dienste

| Dienst | Resolver | Searcher | Auth | Notizen |
|---|---|---|---|---|
| Spotify | Web API, ISRC verfügbar | Web API | Client Credentials (gratis) | Reife Python-Clients |
| Deezer | öffentliche API | öffentliche API | kein Auth | Einfachster Fall |
| Tidal | OpenAPI (openapi.tidal.com), ISRC verfügbar | OpenAPI | Developer-Zugang | Zugang gated; Credentials via Secret |
| YouTube Music | `ytmusicapi` | `ytmusicapi` | Browser-Cookie-Header | Inoffiziell, kann brechen; als Risiko dokumentieren |

### Service-Interface

Jeder Adapter implementiert dasselbe Python-Interface:

```python
class ServiceAdapter(Protocol):
    service_id: str  # "spotify", "deezer", "tidal", "youtube_music"
    capabilities: set[ContentType]  # {TRACK, ALBUM, ARTIST}

    async def resolve(self, url: str) -> ResolvedContent | None:
        """URL → Metadaten + IDs (ISRC/UPC)."""

    async def search(self, meta: ContentMetadata) -> list[SearchHit]:
        """Metadaten → Kandidaten-Treffer mit ID/URL."""

    def matches_url(self, url: str) -> UrlMatch | None:
        """Prüft ob URL zu diesem Service gehört; extrahiert type/id."""
```

Neue Dienste können ohne Änderungen am Kern nachgerüstet werden, solange sie dieses Interface erfüllen.

## Matching-Logik

### Ablauf

```
1. Normalisieren: URL → (source_service, content_type, id)
   ↓ Fehler → HTTP 400 "unsupported_service"
2. Cache-Check: key = f"{source}:{type}:{id}" → Hit → Response
3. Source-Resolve: Adapter holt Metadaten + ISRC/UPC
4. Für jeden Target-Service parallel:
   4a. ID-Match (ISRC für Track, UPC für Album) → Confidence 1.0
   4b. Metadata-Search (Artist + Title [+ Duration]) → Scoring
   4c. Keine Treffer → status = "not_found"
5. Scoring-Aggregation + Cache-Write (TTL 7 Tage)
6. Response
```

### Scoring

Confidence-Berechnung pro Kandidat (nur bei Metadata-Match):

- ID-Match (ISRC/UPC): Confidence = 1.0, Rest irrelevant
- Titel-Ähnlichkeit (Levenshtein-Ratio): 0–1, Gewicht 0.4
- Artist-Overlap (Set-Jaccard über normalisierte Namen): 0–1, Gewicht 0.4
- Dauer-Abweichung (Track): `max(0, 1 - |Δs|/10)`, Gewicht 0.2
- Endgültige Confidence = gewichtete Summe

**Schwellen:**

- ≥ 0.7: Status `ok`, kein Badge
- 0.4–0.7: Status `ok`, UI-Badge `~match`
- < 0.4: Status `not_found`, keine URL zurückgeben

### Artists

Artists haben keinen universellen Code. Matching:

1. Name-Normalisierung (Lowercase, Punctuation-Strip, Umlaut-Normalisierung)
2. Top-3-Treffer pro Dienst
3. Tiebreaker: Genre-Overlap, Top-Track-Überlappung (sofern verfügbar)

Default konservativ: Bei Mehrdeutigkeit lieber `not_found` als falscher Artist.

### Partielle Ergebnisse

Wenn ein Adapter-Call fehlschlägt (Timeout, API-Error), liefert die Response für diesen Dienst `{"status": "error", "message": "..."}`. Andere Dienste werden trotzdem ausgeliefert.

## API-Design

### Endpoints (unter `/api/v1`)

| Method | Path | Zweck |
|---|---|---|
| GET | `/convert` | Haupt-Konvertierung |
| GET | `/c/{short_id}` | Redirect/Response für Short-Link |
| GET | `/services` | Liste unterstützter Dienste und Capabilities |
| GET | `/health` | Liveness/Readiness |
| GET | `/docs` | OpenAPI/Swagger-UI |

### `GET /convert`

**Query-Params:**

- `url` (required): Quell-URL
- `targets` (optional): Komma-Liste von Dienst-IDs; Default: alle
- `share` (optional, bool): Wenn `true`, persistente Short-ID erzeugen und zurückgeben

**Response:**

```json
{
  "source": {
    "service": "tidal",
    "type": "track",
    "id": "123456789",
    "url": "https://tidal.com/...",
    "title": "Nightcall",
    "artists": ["Kavinsky"],
    "album": "Outrun",
    "duration_ms": 225000,
    "isrc": "FR6V81200001",
    "artwork": "https://..."
  },
  "targets": {
    "spotify": { "status": "ok", "url": "...", "confidence": 1.0, "match": "isrc" },
    "deezer":  { "status": "ok", "url": "...", "confidence": 0.92, "match": "metadata" },
    "youtube_music": { "status": "not_found" }
  },
  "cache": { "hit": false, "ttl_seconds": 604800 },
  "share": { "id": "ab3x9k", "url": "https://linkhop.paul.wtf/c/ab3x9k" }
}
```

### Fehlerformat

```json
{ "error": { "code": "unsupported_service", "message": "..." } }
```

Fehler-Codes: `unsupported_service`, `invalid_url`, `rate_limited`, `source_unavailable`, `internal_error`.

### Auth & Rate-Limit

- Anonym: 20 Requests pro Minute pro IP (Default, per Helm-Values änderbar)
- Mit `X-API-Key`-Header: 300 Requests pro Minute (Default, per Helm-Values änderbar)
- Keys werden per CLI auf dem Backend-Pod erstellt:
  - `linkhop-admin key create --note "<freitext>"` → gibt Klartext-Key einmal aus
  - `linkhop-admin key list`
  - `linkhop-admin key revoke <key_id>`
- Keys werden gehasht (bcrypt oder Argon2) in Postgres gespeichert; Lookup per separatem Prefix-Index

### Versionierung

Alle Endpoints unter `/api/v1`. Breaking Changes → neues Prefix `/api/v2`, altes wird deprecated, mindestens 3 Monate parallel laufend.

## UI & UX

### Layout

**Desktop (Layout C):** Cover links (ca. 130 px), Dienst-Liste rechts als vertikale Liste. Input-Feld oben.

**Mobile/Narrow Viewport:** Kollabiert natürlich zu Layout B (Cover oben, Dienste darunter). Breakpoint: ~640 px.

### Zustände

- **Leer:** Großes Eingabefeld, Hint-Text, "Convert"-Button rechts im Feld
- **Loading:** Skeleton-Placeholders für Track-Info und Dienste
- **Result:** Cover + Metadaten links, Dienst-Liste rechts mit "kopieren"- und "öffnen"-Aktionen
- **Error:** Fehler-Message mit Copy-Button für Support/Debug

### Theme

- Catppuccin Mocha (dark) und Latte (light)
- Default: `auto` (folgt `prefers-color-scheme`)
- Toggle oben rechts, drei Zustände: auto/dark/light
- Auswahl in `localStorage` unter `linkhop:theme`
- CSS-Variablen pro Theme; umschaltbar per `data-theme="..."`-Attribut am `<html>`

### Confidence-Anzeige

- `match: "isrc"` oder `match: "upc"` oder `confidence ≥ 0.7`: kein Badge
- `confidence 0.4–0.7`: gelbes `~match`-Badge neben dem Dienst-Namen
- `status: "not_found"`: ausgegraut, kein Link, Text "nicht gefunden"
- `status: "error"`: rot markiert, Tooltip mit Fehler

### Quell-Dienst

Der Quell-Dienst erscheint in der Ergebnis-Liste, aber mit `(Quelle)`-Markierung und nicht als Link. Vermeidet sinnlosen Self-Link.

### Short-Links

- Format: `linkhop.paul.wtf/c/{short_id}` (6 Zeichen, Base62, kollisionsgeprüft)
- Erzeugt beim ersten Aufruf mit `share=true`
- Öffnen einer Short-URL: Frontend-Route, die bei Laden `GET /api/v1/convert?url=<stored_source_url>` ruft und das Ergebnis anzeigt

### Branding

- Name: **linkhop**
- Wort-Mark: `linkhop.` (mit Punkt, immer Lavender)
- Favicon/Logo: in Implementierung entschieden

## Datenmodell

### Postgres

```sql
CREATE TABLE conversions (
  short_id      VARCHAR(12) PRIMARY KEY,
  source_url    TEXT NOT NULL,
  source_service VARCHAR(32) NOT NULL,
  source_type   VARCHAR(16) NOT NULL,
  source_id     VARCHAR(128) NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  access_count  INTEGER NOT NULL DEFAULT 0,
  last_access_at TIMESTAMPTZ,
  UNIQUE (source_service, source_type, source_id)
);

CREATE TABLE api_keys (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key_prefix    VARCHAR(12) NOT NULL UNIQUE,  -- erste 8 Zeichen, für Lookup
  key_hash      TEXT NOT NULL,                -- argon2/bcrypt
  note          TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at    TIMESTAMPTZ,
  rate_limit_override INTEGER  -- optional, überschreibt Default
);
```

Migrationen via Alembic, ausgeführt als initContainer beim Backend-Pod.

### Redis

- `cache:{source}:{type}:{id}` → JSON-Response (TTL konfigurierbar, Default 7 Tage)
- `ratelimit:{ip|key}` → Counter (Window-basiert, z. B. `fastapi-limiter`)

## Deployment

### Chart-Struktur

```
deploy/helm/linkhop/
├── Chart.yaml
├── values.yaml
├── values.schema.json
├── templates/
│   ├── _helpers.tpl
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret-refs.yaml
│   ├── serviceaccount.yaml
│   ├── networkpolicy.yaml
│   └── poddisruptionbudget.yaml
└── charts/                # Subchart: Bitnami Redis
```

### Values-Struktur (Ausschnitt)

```yaml
global:
  domain: linkhop.example.com

backend:
  replicas: 2
  image:
    repository: ghcr.io/<user>/linkhop-backend
    tag: ""  # Default = appVersion aus Chart.yaml
  resources:
    requests: { cpu: 50m,  memory: 128Mi }
    limits:   { cpu: 500m, memory: 512Mi }
  rateLimit:
    anonymousPerMinute: 20
    withKeyPerMinute: 300
  cacheTtlSeconds: 604800
  adapters:
    spotify:      { enabled: true, existingSecret: "" }
    deezer:       { enabled: true }
    tidal:        { enabled: true, existingSecret: "" }
    youtubeMusic: { enabled: true, existingSecret: "" }

frontend:
  replicas: 2
  image:
    repository: ghcr.io/<user>/linkhop-frontend
    tag: ""

redis:                # Bitnami-Subchart
  enabled: true
  architecture: standalone
  auth:
    existingSecret: ""

postgres:             # extern erwartet
  existingSecret: ""  # erwartete Keys: host, port, user, password, database

ingress:
  enabled: true
  className: traefik
  hosts:
    - host: ""        # von global.domain übernommen wenn leer
      paths:
        - path: /
          pathType: Prefix
  annotations: {}     # z.B. external-dns.alpha.kubernetes.io/hostname
  tls:
    enabled: true
    secretName: ""

networkPolicy:
  enabled: true

podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

### Secrets-Pattern

Das Chart erzeugt **keine** API-Credentials. Für jeden konfigurierbaren Adapter erwartet das Chart ein vom Nutzer bereitgestelltes Secret (`existingSecret`). Kompatibel mit `external-secrets`. Erwartete Secret-Keys pro Adapter werden in `values.schema.json` dokumentiert.

### Migrationen

Backend-Pod hat einen `initContainer`, der `alembic upgrade head` ausführt. Migrationen sind idempotent und versioniert im Repo.

### Probes

- Backend: Liveness + Readiness auf `/api/v1/health` (prüft Redis- und Postgres-Verbindung)
- Frontend: Liveness + Readiness auf `/` (statische Seite)

### Publishing

- Container-Images werden via GitHub Actions nach `ghcr.io` gepusht (Tags: SemVer + Git-SHA)
- Helm-Chart wird per `gh-pages` als Helm-Repo veröffentlicht (via `chart-releaser-action`)
- Deployment auf `paulwtf`-Cluster erfolgt über separaten FluxCD-HelmRelease-Commit in `~/git/fluxcd/apps/linkhop/` — das liegt außerhalb dieses Repos

## Testing

- **Unit-Tests** pro Adapter mit Fixture-Daten (keine Live-API-Aufrufe in CI)
- **Integration-Tests** für Matching/Scoring (deterministische Eingaben)
- **Contract-Tests** (optional, manuell triggerbar) gegen echte APIs
- **E2E-Tests** Frontend → Backend → Redis → Postgres mit docker-compose
- **Helm-Tests**: `helm template` + `kubeconform` in CI; `helm test` für Post-Install-Smoke

## Observability

- **Strukturiertes JSON-Logging** (Backend)
- **Prometheus-Metriken** unter `/api/v1/metrics` (`fastapi-prom` oder `prometheus-fastapi-instrumentator`): Request-Count, Latenz-Histogramm pro Endpoint, Adapter-Latenz, Cache-Hit-Rate
- **ServiceMonitor** (Prometheus-Operator) optional im Chart, per `serviceMonitor.enabled`

## Sicherheit

- Keine User-Input-Echo ohne Encoding (XSS)
- API-Keys gehasht gespeichert
- Rate-Limits verpflichtend (vor externem Adapter-Call anwenden, nicht nachher)
- NetworkPolicy default-on: Backend darf Redis/Postgres/Internet; Frontend darf nur nach Backend
- Input-URL-Validierung: Nur URLs bekannter Dienste werden weiterverarbeitet (gegen SSRF)
- CORS: per Values auf `global.domain` beschränkt, optional offen

## Future Work (V2 und darüber hinaus)

Explizit **nicht** Teil von V1. Wird in eigener Spec-Runde durchgeplant, wenn V1 stabil läuft.

- **User-System via OIDC/Authentik** (keine eigene Auth bauen)
- **Self-Service API-Key-Management** (User-Panel)
- **Admin-Panel** für User-/Key-Verwaltung, Quotas, Audit-Log
- **Apple Music**-Adapter (Developer-Account-Voraussetzung)
- **Playlists**-Support (Track-für-Track-Auflösung)
- **Stats-Endpoint** (populäre Konvertierungen, Top-Tracks etc.)
- **Zusätzliche Dienste**: YouTube (nicht nur YT Music), Amazon Music — sofern APIs zugänglich werden
- **User-Spalte** (`user_id`) in `conversions`/`api_keys`-Tabellen — wird beim V1-Schema bereits mitgedacht, aber erst mit V2 aktiv genutzt

## Offene Punkte (vor Implementierung zu klären)

- Konkrete Tidal-Developer-Registrierung (Paul)
- Spotify Client-ID/Secret (Paul)
- YT-Music: Cookie-basierte Auth via `ytmusicapi` → wie in Kubernetes rotieren? (Secret-basiert, manuell zu aktualisieren; dokumentieren)
- Logo/Favicon-Entwurf
- Domain-Pinning: `linkhop.paul.wtf` bestätigt?
