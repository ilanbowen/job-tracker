{{- define "job-tracker.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "job-tracker.fullname" -}}
{{- .Release.Name -}}
{{- end -}}

{{- define "job-tracker.labels" -}}
app.kubernetes.io/name: {{ include "job-tracker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "job-tracker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "job-tracker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "job-tracker.namespace" -}}
{{- default .Release.Namespace .Values.namespaceOverride -}}
{{- end -}}

{{- define "job-tracker.databaseUrl" -}}
postgresql+psycopg2://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@{{ include "job-tracker.fullname" . }}-postgres:{{ .Values.postgres.port }}/{{ .Values.postgres.database }}
{{- end -}}
