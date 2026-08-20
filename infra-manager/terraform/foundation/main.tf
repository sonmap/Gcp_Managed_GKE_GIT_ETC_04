data "google_compute_network" "existing" {
  project = var.project_id
  name    = var.network_name
}

data "google_compute_subnetwork" "existing" {
  project = var.project_id
  region  = var.region
  name    = var.subnetwork_name
}

resource "google_container_cluster" "analysis" {
  project  = var.project_id
  name     = var.cluster_name
  location = var.region

  enable_autopilot = true

  network         = data.google_compute_network.existing.id
  subnetwork      = data.google_compute_subnetwork.existing.id
  networking_mode = "VPC_NATIVE"

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
  }

  # GKE Autopilot is VPC-native. Empty CIDR values allow GKE to allocate ranges
  # compatible with the existing subnet, matching the validated PoC behavior.
  ip_allocation_policy {
    cluster_ipv4_cidr_block  = ""
    services_ipv4_cidr_block = ""
  }

  release_channel {
    channel = upper(var.release_channel)
  }

  deletion_protection = false

  resource_labels = {
    managed_by = "infra-manager"
    purpose    = "data-model-analysis"
  }
}
