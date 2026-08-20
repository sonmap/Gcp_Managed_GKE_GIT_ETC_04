terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30, < 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6, < 4.0"
    }
  }
}

provider "google" {
  project = var.target_project_id
}

data "google_client_config" "current" {}

data "google_container_cluster" "analysis" {
  project  = var.gke_project_id != "" ? var.gke_project_id : var.target_project_id
  name     = var.gke_cluster_name
  location = var.gke_location
}

provider "kubernetes" {
  host                   = "https://${data.google_container_cluster.analysis.endpoint}"
  token                  = data.google_client_config.current.access_token
  cluster_ca_certificate = base64decode(data.google_container_cluster.analysis.master_auth[0].cluster_ca_certificate)
}
