output "im_execution_service_account" {
  value       = google_service_account.im_exec.email
  description = "Infrastructure Manager execution service account"
}

output "cloud_run_adapter_service_account" {
  value       = google_service_account.adapter.email
  description = "Cloud Run adapter service account"
}
