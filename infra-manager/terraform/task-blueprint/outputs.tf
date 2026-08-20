output "dataset_id" {
  value       = google_bigquery_dataset.task.dataset_id
  description = "Created BigQuery dataset ID"
}

output "namespace" {
  value       = kubernetes_namespace_v1.task.metadata[0].name
  description = "Created GKE namespace"
}

output "gsa_email" {
  value       = google_service_account.task.email
  description = "Per-task Google Service Account"
}

output "ksa_name" {
  value       = kubernetes_service_account_v1.jupyter.metadata[0].name
  description = "Per-task Kubernetes Service Account"
}

output "jupyter_service" {
  value       = kubernetes_service_v1.jupyter.metadata[0].name
  description = "Jupyter Kubernetes Service name"
}

output "jupyter_service_type" {
  value       = var.jupyter_service_type
  description = "Jupyter Kubernetes Service type"
}

output "jupyter_token_secret" {
  value       = kubernetes_secret_v1.jupyter.metadata[0].name
  description = "Kubernetes Secret that stores the generated Jupyter token"
}

output "pvc_name" {
  value       = kubernetes_persistent_volume_claim_v1.jupyter.metadata[0].name
  description = "Jupyter workspace PVC"
}
