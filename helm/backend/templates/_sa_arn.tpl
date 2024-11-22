{{/*
Get the service account role ARN
*/}}
{{- define "backend.serviceAccountRoleArn" -}}
{{- $sa := (lookup "v1" "ServiceAccount" .Release.Namespace "backend-sa") -}}
{{- if and $sa $sa.metadata.annotations -}}
    {{- index $sa.metadata.annotations "eks.amazonaws.com/role-arn" -}}
{{- else -}}
    {{- .Values.serviceAccount.roleArn -}}
{{- end -}}
{{- end -}}
