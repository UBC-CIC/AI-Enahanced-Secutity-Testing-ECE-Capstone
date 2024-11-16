{{/*
Generate a unique name for the Job based on the current time.
*/}}
{{- define "zap.scan.jobName" -}}
{{ printf "%s-%s" .Values.job.name (now | date "20060102150405") }}
{{- end -}}
