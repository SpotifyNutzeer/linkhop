# LinkHop Helm Chart — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a portable, monolithic Helm chart that deploys the full LinkHop stack (Backend, Frontend, Ingress, Alembic migrations) on any Kubernetes cluster.

**Architecture:** Single Helm chart under `helm/linkhop/` with two Deployments (backend + frontend), an Ingress with path-based routing, a pre-install/pre-upgrade migration Job, and an optional Bitnami Redis subchart. PostgreSQL is external-only. Secrets follow the `existingSecret` pattern.

**Tech Stack:** Helm 3, Kubernetes standard APIs (apps/v1, networking.k8s.io/v1, batch/v1), Bitnami Redis subchart 20.x

**Spec:** `docs/superpowers/specs/2026-04-21-helm-chart-design.md`

---

### Task 1: Chart Scaffolding

**Files:**
- Create: `helm/linkhop/Chart.yaml`
- Create: `helm/linkhop/.helmignore`

- [ ] **Step 1: Create Chart.yaml**

```yaml
apiVersion: v2
name: linkhop
description: Music-link converter across streaming services
type: application
version: 0.1.0
appVersion: "0.1.0"

dependencies:
  - name: redis
    version: "~20.x"
    repository: https://charts.bitnami.com/bitnami
    condition: redis.enabled
```

- [ ] **Step 2: Create .helmignore**

```
.git
.gitignore
*.md
```

- [ ] **Step 3: Pull Redis dependency**

Run: `cd helm/linkhop && helm dependency update`
Expected: `charts/redis-20.x.x.tgz` created, `Chart.lock` generated.

- [ ] **Step 4: Commit**

```bash
git add helm/linkhop/Chart.yaml helm/linkhop/Chart.lock helm/linkhop/.helmignore helm/linkhop/charts/
git commit -m "feat(helm): scaffold chart with Redis subchart dependency"
```

---

### Task 2: Template Helpers

**Files:**
- Create: `helm/linkhop/templates/_helpers.tpl`

- [ ] **Step 1: Write _helpers.tpl**

```gotemplate
{{/*
Chart name, truncated to 63 chars (k8s label limit).
*/}}
{{- define "linkhop.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name. Uses fullnameOverride if set, otherwise
<release>-<chart> (or just <release> if release == chart name).
*/}}
{{- define "linkhop.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "linkhop.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{ include "linkhop.selectorLabels" . }}
{{- end }}

{{/*
Selector labels (shared between all components).
*/}}
{{- define "linkhop.selectorLabels" -}}
app.kubernetes.io/name: {{ include "linkhop.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend selector labels.
*/}}
{{- define "linkhop.backendSelectorLabels" -}}
{{ include "linkhop.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend selector labels.
*/}}
{{- define "linkhop.frontendSelectorLabels" -}}
{{ include "linkhop.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Name of the Secret to use. Returns existingSecret if set, otherwise
the generated name.
*/}}
{{- define "linkhop.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "linkhop.fullname" . }}
{{- end }}
{{- end }}

{{/*
Redis URL. When the bundled subchart is active, build the URL from the
release-scoped service name. Otherwise fall back to externalRedis.url.
*/}}
{{- define "linkhop.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s-redis-master:6379/0" .Release.Name }}
{{- else }}
{{- required "externalRedis.url is required when redis.enabled=false" .Values.externalRedis.url }}
{{- end }}
{{- end }}
```

- [ ] **Step 2: Commit**

```bash
git add helm/linkhop/templates/_helpers.tpl
git commit -m "feat(helm): add template helpers"
```

---

### Task 3: Secret Template

**Files:**
- Create: `helm/linkhop/templates/secret.yaml`

- [ ] **Step 1: Write secret.yaml**

```gotemplate
{{- if not .Values.secrets.existingSecret }}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "linkhop.fullname" . }}
  labels:
    {{- include "linkhop.labels" . | nindent 4 }}
type: Opaque
stringData:
  LINKHOP_DATABASE_URL: {{ required "config.databaseUrl is required" .Values.config.databaseUrl | quote }}
  LINKHOP_REDIS_URL: {{ include "linkhop.redisUrl" . | quote }}
  LINKHOP_SPOTIFY_CLIENT_ID: {{ .Values.secrets.spotifyClientId | quote }}
  LINKHOP_SPOTIFY_CLIENT_SECRET: {{ .Values.secrets.spotifyClientSecret | quote }}
  LINKHOP_TIDAL_CLIENT_ID: {{ .Values.secrets.tidalClientId | quote }}
  LINKHOP_TIDAL_CLIENT_SECRET: {{ .Values.secrets.tidalClientSecret | quote }}
{{- end }}
```

- [ ] **Step 2: Commit**

```bash
git add helm/linkhop/templates/secret.yaml
git commit -m "feat(helm): add secret template"
```

---

### Task 4: Backend Deployment + Service

**Files:**
- Create: `helm/linkhop/templates/backend-deployment.yaml`
- Create: `helm/linkhop/templates/backend-service.yaml`

- [ ] **Step 1: Write backend-deployment.yaml**

```gotemplate
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "linkhop.fullname" . }}-backend
  labels:
    {{- include "linkhop.labels" . | nindent 4 }}
    app.kubernetes.io/component: backend
spec:
  replicas: {{ .Values.backend.replicas }}
  selector:
    matchLabels:
      {{- include "linkhop.backendSelectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "linkhop.backendSelectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: backend
          image: "{{ .Values.backend.image.repository }}:{{ .Values.backend.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.backend.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          envFrom:
            - secretRef:
                name: {{ include "linkhop.secretName" . }}
          env:
            - name: LINKHOP_LOG_LEVEL
              value: {{ .Values.config.logLevel | quote }}
            - name: LINKHOP_CORS_ALLOW_ORIGINS
              value: {{ .Values.config.corsAllowOrigins | quote }}
            - name: LINKHOP_RATE_ANONYMOUS
              value: {{ .Values.config.rateAnonymous | quote }}
            - name: LINKHOP_RATE_WITH_KEY
              value: {{ .Values.config.rateWithKey | quote }}
            - name: LINKHOP_CACHE_TTL
              value: {{ .Values.config.cacheTtl | quote }}
            - name: LINKHOP_ENABLE_SPOTIFY
              value: {{ .Values.config.enableSpotify | quote }}
            - name: LINKHOP_ENABLE_DEEZER
              value: {{ .Values.config.enableDeezer | quote }}
            - name: LINKHOP_ENABLE_TIDAL
              value: {{ .Values.config.enableTidal | quote }}
            - name: LINKHOP_FORWARDED_ALLOW_IPS
              value: {{ .Values.backend.forwardedAllowIps | quote }}
          livenessProbe:
            httpGet:
              path: /api/v1/health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 30
            timeoutSeconds: 3
          readinessProbe:
            httpGet:
              path: /api/v1/health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
          {{- with .Values.backend.resources }}
          resources:
            {{- toYaml . | nindent 12 }}
          {{- end }}
      {{- with .Values.backend.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.backend.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.backend.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

- [ ] **Step 2: Write backend-service.yaml**

```gotemplate
apiVersion: v1
kind: Service
metadata:
  name: {{ include "linkhop.fullname" . }}-backend
  labels:
    {{- include "linkhop.labels" . | nindent 4 }}
    app.kubernetes.io/component: backend
spec:
  type: ClusterIP
  ports:
    - port: 8080
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "linkhop.backendSelectorLabels" . | nindent 4 }}
```

- [ ] **Step 3: Commit**

```bash
git add helm/linkhop/templates/backend-deployment.yaml helm/linkhop/templates/backend-service.yaml
git commit -m "feat(helm): add backend deployment and service"
```

---

### Task 5: Frontend Deployment + Service

**Files:**
- Create: `helm/linkhop/templates/frontend-deployment.yaml`
- Create: `helm/linkhop/templates/frontend-service.yaml`

- [ ] **Step 1: Write frontend-deployment.yaml**

```gotemplate
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "linkhop.fullname" . }}-frontend
  labels:
    {{- include "linkhop.labels" . | nindent 4 }}
    app.kubernetes.io/component: frontend
spec:
  replicas: {{ .Values.frontend.replicas }}
  selector:
    matchLabels:
      {{- include "linkhop.frontendSelectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "linkhop.frontendSelectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: frontend
          image: "{{ .Values.frontend.image.repository }}:{{ .Values.frontend.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.frontend.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 80
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 5
            periodSeconds: 30
            timeoutSeconds: 3
          readinessProbe:
            httpGet:
              path: /
              port: http
            initialDelaySeconds: 3
            periodSeconds: 10
            timeoutSeconds: 3
          {{- with .Values.frontend.resources }}
          resources:
            {{- toYaml . | nindent 12 }}
          {{- end }}
      {{- with .Values.frontend.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.frontend.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.frontend.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

- [ ] **Step 2: Write frontend-service.yaml**

```gotemplate
apiVersion: v1
kind: Service
metadata:
  name: {{ include "linkhop.fullname" . }}-frontend
  labels:
    {{- include "linkhop.labels" . | nindent 4 }}
    app.kubernetes.io/component: frontend
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "linkhop.frontendSelectorLabels" . | nindent 4 }}
```

- [ ] **Step 3: Commit**

```bash
git add helm/linkhop/templates/frontend-deployment.yaml helm/linkhop/templates/frontend-service.yaml
git commit -m "feat(helm): add frontend deployment and service"
```

---

### Task 6: Ingress

**Files:**
- Create: `helm/linkhop/templates/ingress.yaml`

- [ ] **Step 1: Write ingress.yaml**

```gotemplate
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "linkhop.fullname" . }}
  labels:
    {{- include "linkhop.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.ingress.className }}
  ingressClassName: {{ .Values.ingress.className | quote }}
  {{- end }}
  {{- if .Values.ingress.tls.enabled }}
  tls:
    - hosts:
        - {{ .Values.ingress.host | quote }}
      secretName: {{ .Values.ingress.tls.secretName | quote }}
  {{- end }}
  rules:
    - host: {{ .Values.ingress.host | quote }}
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: {{ include "linkhop.fullname" . }}-backend
                port:
                  number: 8080
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ include "linkhop.fullname" . }}-frontend
                port:
                  number: 80
{{- end }}
```

- [ ] **Step 2: Commit**

```bash
git add helm/linkhop/templates/ingress.yaml
git commit -m "feat(helm): add ingress with path-based routing"
```

---

### Task 7: Migration Job

**Files:**
- Create: `helm/linkhop/templates/migration-job.yaml`

- [ ] **Step 1: Write migration-job.yaml**

The Alembic `env.py` reads `LINKHOP_DATABASE_URL` via `Settings()` (pydantic-settings). The working directory must contain `alembic.ini` — the Dockerfile already copies it to `/app/alembic.ini`. The command `alembic upgrade head` picks it up from CWD.

```gotemplate
{{- if .Values.migration.enabled }}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "linkhop.fullname" . }}-migrate
  labels:
    {{- include "linkhop.labels" . | nindent 4 }}
    app.kubernetes.io/component: migration
  annotations:
    helm.sh/hook: pre-install,pre-upgrade
    helm.sh/hook-weight: "-5"
    helm.sh/hook-delete-policy: before-hook-creation
spec:
  backoffLimit: 1
  template:
    metadata:
      labels:
        {{- include "linkhop.backendSelectorLabels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      restartPolicy: Never
      containers:
        - name: migrate
          image: "{{ .Values.backend.image.repository }}:{{ .Values.backend.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.backend.image.pullPolicy }}
          command: ["alembic", "upgrade", "head"]
          workingDir: /app
          env:
            - name: LINKHOP_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ include "linkhop.secretName" . }}
                  key: LINKHOP_DATABASE_URL
{{- end }}
```

- [ ] **Step 2: Commit**

```bash
git add helm/linkhop/templates/migration-job.yaml
git commit -m "feat(helm): add Alembic migration hook job"
```

---

### Task 8: values.yaml + NOTES.txt

**Files:**
- Create: `helm/linkhop/values.yaml`
- Create: `helm/linkhop/templates/NOTES.txt`

- [ ] **Step 1: Write values.yaml**

```yaml
# -- Backend
backend:
  image:
    repository: ghcr.io/OWNER/linkhop-backend
    # -- Defaults to Chart.appVersion
    tag: ""
    pullPolicy: IfNotPresent
  replicas: 1
  resources: {}
  nodeSelector: {}
  tolerations: []
  affinity: {}
  # -- Passed as LINKHOP_FORWARDED_ALLOW_IPS to uvicorn.
  # Set to "*" so the Ingress controller's X-Forwarded-For is trusted.
  forwardedAllowIps: "*"

# -- Frontend
frontend:
  image:
    repository: ghcr.io/OWNER/linkhop-frontend
    # -- Defaults to Chart.appVersion
    tag: ""
    pullPolicy: IfNotPresent
  replicas: 1
  resources: {}
  nodeSelector: {}
  tolerations: []
  affinity: {}

# -- Ingress
ingress:
  enabled: true
  # -- Set to your cluster's ingress class (e.g. "traefik", "nginx")
  className: ""
  # -- Hostname for the Ingress rule
  host: ""
  annotations: {}
  tls:
    enabled: false
    # -- Name of TLS Secret (cert-manager can create this automatically)
    secretName: ""

# -- Application config (non-sensitive, set as plain env vars)
config:
  # -- PostgreSQL connection string (required)
  databaseUrl: ""
  logLevel: INFO
  corsAllowOrigins: "*"
  rateAnonymous: 20
  rateWithKey: 300
  cacheTtl: 604800
  enableSpotify: true
  enableDeezer: true
  enableTidal: true

# -- Sensitive credentials
secrets:
  spotifyClientId: ""
  spotifyClientSecret: ""
  tidalClientId: ""
  tidalClientSecret: ""
  # -- Use an existing Secret instead of creating one.
  # The Secret must contain keys: LINKHOP_DATABASE_URL, LINKHOP_REDIS_URL,
  # LINKHOP_SPOTIFY_CLIENT_ID, LINKHOP_SPOTIFY_CLIENT_SECRET,
  # LINKHOP_TIDAL_CLIENT_ID, LINKHOP_TIDAL_CLIENT_SECRET
  existingSecret: ""

# -- Alembic database migrations (pre-install/pre-upgrade hook)
migration:
  enabled: true

# -- External Redis (only used when redis.enabled=false)
externalRedis:
  # -- Redis connection URL (e.g. redis://my-redis:6379/0)
  url: ""

# -- Bitnami Redis subchart
# @default -- standalone, no auth, no persistence (cache-only)
redis:
  enabled: true
  architecture: standalone
  auth:
    enabled: false
  master:
    persistence:
      enabled: false

# -- Pull secrets for private container registries
imagePullSecrets: []
nameOverride: ""
fullnameOverride: ""
```

- [ ] **Step 2: Write NOTES.txt**

```gotemplate
LinkHop has been deployed!

{{- if .Values.ingress.enabled }}
Application URL:
  {{- if .Values.ingress.tls.enabled }}
  https://{{ .Values.ingress.host }}
  {{- else }}
  http://{{ .Values.ingress.host }}
  {{- end }}
{{- else }}
No Ingress configured. Access via port-forward:
  kubectl port-forward svc/{{ include "linkhop.fullname" . }}-frontend 8080:80
{{- end }}

{{- if not .Values.config.databaseUrl }}

WARNING: config.databaseUrl is not set. The backend will fail to start.
Set it via --set config.databaseUrl=postgresql+asyncpg://...
{{- end }}

{{- if .Values.secrets.existingSecret }}

Using existing Secret: {{ .Values.secrets.existingSecret }}
Ensure it contains the required keys (see values.yaml for the list).
{{- end }}
```

- [ ] **Step 3: Commit**

```bash
git add helm/linkhop/values.yaml helm/linkhop/templates/NOTES.txt
git commit -m "feat(helm): add values.yaml and NOTES.txt"
```

---

### Task 9: Lint and Template Validation

**Files:** None (validation only)

- [ ] **Step 1: Lint the chart**

Run: `helm lint helm/linkhop/ --set config.databaseUrl=postgresql+asyncpg://test:test@db:5432/test`
Expected: `0 chart(s) failed` — may show INFO about missing ingress.host, that's fine.

- [ ] **Step 2: Template render — default values**

Run: `helm template test helm/linkhop/ --set config.databaseUrl=postgresql+asyncpg://test:test@db:5432/test 2>&1 | head -200`
Expected: Valid YAML output with all resources (2 Deployments, 2 Services, 1 Ingress, 1 Secret, 1 Job, Redis resources).

- [ ] **Step 3: Template render — existingSecret, Redis disabled**

Run: `helm template test helm/linkhop/ --set secrets.existingSecret=my-secret --set redis.enabled=false --set externalRedis.url=redis://ext:6379/0 --set config.databaseUrl=postgresql+asyncpg://x:x@db:5432/x`
Expected: No Secret resource generated. No Redis resources. Backend/Frontend Deployments reference `my-secret`.

- [ ] **Step 4: Template render — ingress disabled**

Run: `helm template test helm/linkhop/ --set ingress.enabled=false --set config.databaseUrl=postgresql+asyncpg://x:x@db:5432/x`
Expected: No Ingress resource in output.

- [ ] **Step 5: Fix any issues found in steps 1-4**

If any step fails, fix the relevant template and re-run. No commit needed — previous tasks already committed the files.

- [ ] **Step 6: Commit any fixes**

Only if changes were made in step 5:
```bash
git add helm/linkhop/
git commit -m "fix(helm): address lint and template issues"
```

---

### Task 10: Dry-Run Against Live Cluster

**Files:** None (validation only)

- [ ] **Step 1: Verify cluster access**

Run: `kubectl cluster-info`
Expected: Cluster endpoint shown, connection works.

- [ ] **Step 2: Dry-run install**

Run: `helm install linkhop helm/linkhop/ --namespace linkhop --create-namespace --dry-run --set config.databaseUrl=postgresql+asyncpg://test:test@db:5432/test --set ingress.host=linkhop.example.com`
Expected: All resources render, no server-side validation errors.

- [ ] **Step 3: Review rendered output**

Manually check:
- Ingress paths: `/api` → backend:8080, `/` → frontend:80
- Secret has all 6 expected keys
- Migration Job has correct hook annotations
- Redis Deployment is present (standalone, no auth)
- Labels and selectors are consistent

No commit — this is validation only.
