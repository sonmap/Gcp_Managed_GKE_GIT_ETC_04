output "cluster_name" {
  value       = google_container_cluster.analysis.name
  description = "Shared GKE Autopilot cluster name"
}

output "cluster_location" {
  value       = google_container_cluster.analysis.location
  description = "Shared GKE Autopilot cluster location"
}

output "cluster_endpoint" {
  value       = google_container_cluster.analysis.endpoint
  description = "GKE control plane endpoint"
  sensitive   = true
}
