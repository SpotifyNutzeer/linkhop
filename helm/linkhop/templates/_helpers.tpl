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
