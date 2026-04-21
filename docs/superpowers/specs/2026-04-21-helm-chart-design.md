# linkhop Helm Chart — Design-Spezifikation

**Datum:** 2026-04-21
**Status:** Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (brainstorming mit Claude)

## Überblick

Ein monolithisches Helm Chart für das Deployment der gesamten LinkHop-Anwendung auf beliebigen Kubernetes-Clustern. Das Chart deployt Backend (FastAPI) und Frontend (Nginx/SvelteKit) als separate Deployments, stellt Ingress-Routing bereit und beinhaltet optional Redis als Bitnami-Subchart. PostgreSQL wird extern erwartet.

### Designziele

- **Generisch einsetzbar** — kein fester Ingress-Controller, keine clusterspezifischen Annahmen
- **Sinnvolle Defaults** — funktioniert out-of-the-box mit minimalem values-Override
- **Secrets-Hygiene** — Credentials werden in einem Kubernetes Secret verwaltet, nicht in ConfigMaps; existierende Secrets können referenziert werden
- **DB-Migrationen als Hook** — Alembic läuft als pre-upgrade/pre-install Job

### Nicht-Ziele

- Kein PostgreSQL-Subchart (extern erwartet, operativ anspruchsvoller)
- Kein HPA (Replicas als statischer Wert, kann bei Bedarf ergänzt werden)
- Kein ServiceMonitor / PrometheusRule (Future Work)
- Kein NetworkPolicy (Future Work)

## Chart-Struktur

```
helm/linkhop/
├── Chart.yaml              # Chart-Metadaten + Redis-Dependency
├── Chart.lock
├── values.yaml             # Alle konfigurierbaren Werte
├── templates/
│   ├── _helpers.tpl        # Name/Label-Helper, Common Labels
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── ingress.yaml
│   ├── migration-job.yaml  # Helm pre-install/pre-upgrade Hook
│   ├── secret.yaml         # Nur wenn kein existingSecret gesetzt
│   └── NOTES.txt           # Post-install Hinweise
└── charts/                 # Bitnami Redis Subchart (auto via dependency)
```

## Komponenten-Details

### Backend-Deployment

- **Image:** Konfigurierbar, Default `ghcr.io/OWNER/linkhop-backend:latest`
- **Port:** 8080 (fest, passend zum Dockerfile CMD)
- **Env-Vars:** Alle `LINKHOP_`-prefixed Variablen, referenziert aus dem Secret
  - `LINKHOP_DATABASE_URL` — Pflicht, externe PostgreSQL-Verbindung
  - `LINKHOP_REDIS_URL` — wird automatisch auf den internen Redis-Service gesetzt wenn `redis.enabled=true`, sonst aus `externalRedis.url`
  - `LINKHOP_SPOTIFY_CLIENT_ID`, `LINKHOP_SPOTIFY_CLIENT_SECRET`
  - `LINKHOP_TIDAL_CLIENT_ID`, `LINKHOP_TIDAL_CLIENT_SECRET`
  - `LINKHOP_ENABLE_SPOTIFY`, `LINKHOP_ENABLE_DEEZER`, `LINKHOP_ENABLE_TIDAL`
  - `LINKHOP_CORS_ALLOW_ORIGINS`, `LINKHOP_LOG_LEVEL`
  - `LINKHOP_RATE_ANONYMOUS`, `LINKHOP_RATE_WITH_KEY`, `LINKHOP_CACHE_TTL`
  - `LINKHOP_FORWARDED_ALLOW_IPS` — Default im Dockerfile ist `127.0.0.1`; im Cluster muss das auf den Pod-CIDR-Range oder `*` gesetzt werden, damit uvicorn dem `X-Forwarded-For` vom Ingress vertraut
- **Probes:**
  - Liveness: HTTP GET `/api/v1/health`, initialDelaySeconds: 10
  - Readiness: HTTP GET `/api/v1/health`, initialDelaySeconds: 5
- **Resources:** Konfigurierbar, kein Default (Operator entscheidet)
- **Scheduling:** `nodeSelector`, `tolerations`, `affinity` konfigurierbar
- **Service:** ClusterIP auf Port 8080

### Frontend-Deployment

- **Image:** Konfigurierbar, Default `ghcr.io/OWNER/linkhop-frontend:latest`
- **Port:** 80 (nginx)
- **Probes:**
  - Liveness: HTTP GET `/`, initialDelaySeconds: 5
  - Readiness: HTTP GET `/`, initialDelaySeconds: 3
- **Resources:** Konfigurierbar, kein Default
- **Scheduling:** `nodeSelector`, `tolerations`, `affinity` konfigurierbar
- **Service:** ClusterIP auf Port 80

### Ingress

- **Standardmäßig aktiviert** (`ingress.enabled: true`)
- **Kein fester `ingressClassName`** — muss vom Operator gesetzt werden (Traefik, nginx, etc.)
- **Routing-Regeln:**
  - `<host>/api/*` → Backend-Service:8080
  - `<host>/*` → Frontend-Service:80
- **TLS:** Optional, konfigurierbar über `ingress.tls`
  - `secretName` für cert-manager oder manuell hinterlegtes Zertifikat
  - cert-manager-Annotation (`cert-manager.io/cluster-issuer`) über `ingress.annotations` setzbar
- **Annotations:** Frei konfigurierbar für beliebige Ingress-Controller-Features

### Migration-Job (Alembic)

- **Helm Hook:** `pre-install,pre-upgrade` mit `hook-weight: "-5"` (läuft vor den Deployments)
- **Hook Delete Policy:** `before-hook-creation` (alter Job wird vor neuem Lauf gelöscht)
- **Image:** Nutzt das Backend-Image (gleiche Version = gleiche Migrationen)
- **Command:** `alembic upgrade head`
- **Env:** Nur `LINKHOP_DATABASE_URL` aus dem Secret
- **Deaktivierbar:** `migration.enabled: false` für Umgebungen mit extern verwalteten Migrationen
- **restartPolicy:** `Never`, `backoffLimit: 1`

### Secret

- Wird nur erstellt wenn `secrets.existingSecret` leer ist
- Enthält alle sensitiven und nicht-sensitiven `LINKHOP_`-Env-Vars
- Bei `secrets.existingSecret: "my-secret"` wird stattdessen dieses Secret in allen Deployments und Jobs referenziert — der Operator ist verantwortlich, dass es die erwarteten Keys enthält

### Redis (Bitnami Subchart)

- **Dependency in Chart.yaml:**
  ```yaml
  dependencies:
    - name: redis
      version: "~20.x"    # aktuelle Bitnami-Major
      repository: oci://registry-1.docker.io/bitnamicharts
      condition: redis.enabled
  ```
- **Defaults:** Standalone-Architektur, kein Auth, keine Persistence (reiner Cache)
- **Deaktivierbar:** `redis.enabled: false` + `externalRedis.url` für eigene Redis-Instanz
- **Redis-URL-Auflösung im Backend:**
  - `redis.enabled=true` → Template generiert URL automatisch: `redis://{{ release }}-redis-master:6379/0`
  - `redis.enabled=false` → `externalRedis.url` wird verwendet

## values.yaml

```yaml
# -- Backend-Konfiguration
backend:
  image:
    repository: ghcr.io/OWNER/linkhop-backend
    tag: ""              # Default: .Chart.AppVersion
    pullPolicy: IfNotPresent
  replicas: 1
  resources: {}
  nodeSelector: {}
  tolerations: []
  affinity: {}
  # -- Override für LINKHOP_FORWARDED_ALLOW_IPS (Default im Image: 127.0.0.1)
  forwardedAllowIps: "*"

# -- Frontend-Konfiguration
frontend:
  image:
    repository: ghcr.io/OWNER/linkhop-frontend
    tag: ""              # Default: .Chart.AppVersion
    pullPolicy: IfNotPresent
  replicas: 1
  resources: {}
  nodeSelector: {}
  tolerations: []
  affinity: {}

# -- Ingress-Konfiguration
ingress:
  enabled: true
  className: ""
  host: ""
  annotations: {}
  tls:
    enabled: false
    secretName: ""

# -- Anwendungs-Konfiguration (nicht-sensitiv)
config:
  databaseUrl: ""                  # Pflicht: postgresql+asyncpg://...
  logLevel: INFO
  corsAllowOrigins: "*"
  rateAnonymous: 20
  rateWithKey: 300
  cacheTtl: 604800
  enableSpotify: true
  enableDeezer: true
  enableTidal: true

# -- Secrets (sensitiv)
secrets:
  spotifyClientId: ""
  spotifyClientSecret: ""
  tidalClientId: ""
  tidalClientSecret: ""
  # -- Existierendes Secret referenzieren statt ein neues zu erstellen
  existingSecret: ""

# -- DB-Migration (Alembic)
migration:
  enabled: true

# -- Externer Redis (nur wenn redis.enabled=false)
externalRedis:
  url: ""

# -- Bitnami Redis Subchart
redis:
  enabled: true
  architecture: standalone
  auth:
    enabled: false
  master:
    persistence:
      enabled: false

# -- Globale Einstellungen
imagePullSecrets: []
nameOverride: ""
fullnameOverride: ""
```

## Template-Helpers (_helpers.tpl)

Standardmäßige Helm-Helper:

- `linkhop.name` — Chart-Name (mit nameOverride)
- `linkhop.fullname` — Release-spezifischer Name (mit fullnameOverride)
- `linkhop.labels` — Common Labels (app.kubernetes.io/name, instance, version, managed-by)
- `linkhop.selectorLabels` — Selector Labels (name + instance)
- `linkhop.backendSelectorLabels` — Backend-spezifisch (+ component: backend)
- `linkhop.frontendSelectorLabels` — Frontend-spezifisch (+ component: frontend)
- `linkhop.redisUrl` — Berechnet die Redis-URL basierend auf `redis.enabled`
- `linkhop.secretName` — Gibt `existingSecret` oder den generierten Secret-Namen zurück

## Ingress Routing-Detail

```
Host: {{ .Values.ingress.host }}

  /api/*   →  backend-service:8080   (pathType: Prefix, path: /api)
  /*       →  frontend-service:80    (pathType: Prefix, path: /)
```

Die Reihenfolge ist wichtig: `/api` muss vor `/` stehen, damit der Ingress-Controller den spezifischeren Pfad bevorzugt.

## Secret-Struktur

Keys im Secret (sowohl generiert als auch bei existingSecret erwartet):

```
LINKHOP_DATABASE_URL
LINKHOP_REDIS_URL
LINKHOP_SPOTIFY_CLIENT_ID
LINKHOP_SPOTIFY_CLIENT_SECRET
LINKHOP_TIDAL_CLIENT_ID
LINKHOP_TIDAL_CLIENT_SECRET
```

Nicht-sensitive Config-Werte (`LOG_LEVEL`, `CORS_ALLOW_ORIGINS`, etc.) werden direkt als `env`-Einträge im Deployment-Template gesetzt, nicht im Secret.

## NOTES.txt

Nach `helm install` zeigt NOTES.txt:

1. Die URL unter der LinkHop erreichbar ist (aus Ingress-Host)
2. Hinweis, dass `config.databaseUrl` gesetzt sein muss
3. Hinweis zum existingSecret-Pattern falls verwendet
