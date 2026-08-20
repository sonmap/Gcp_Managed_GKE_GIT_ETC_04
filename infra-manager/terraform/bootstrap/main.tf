data "google_project" "current" {
  project_id = var.project_id
}

resource "google_service_account" "im_exec" {
  project      = var.project_id
  account_id   = var.im_exec_account_id
  display_name = "Infrastructure Manager execution"
}

resource "google_service_account" "adapter" {
  project      = var.project_id
  account_id   = var.adapter_account_id
  display_name = "Cloud Run Infrastructure Manager adapter"
}

locals {
  im_exec_roles = toset([
    "roles/config.agent",
    "roles/container.admin",
    "roles/compute.viewer",
    "roles/bigquery.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.securityAdmin",
    "roles/resourcemanager.projectIamAdmin"
  ])
}

resource "google_project_iam_member" "im_exec_roles" {
  for_each = local.im_exec_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.im_exec.email}"
}

resource "google_project_iam_member" "adapter_config_admin" {
  project = var.project_id
  role    = "roles/config.admin"
  member  = "serviceAccount:${google_service_account.adapter.email}"
}

# The adapter asks Infrastructure Manager to execute Terraform as im_exec.
resource "google_service_account_iam_member" "adapter_act_as_im_exec" {
  service_account_id = google_service_account.im_exec.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.adapter.email}"
}

# GKE Autopilot uses the project's default Compute Engine service account unless
# a different node identity is configured. The IM execution SA must be able to
# act as that service account when creating the cluster.
resource "google_service_account_iam_member" "im_exec_act_as_default_compute" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${data.google_project.current.number}-compute@developer.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.im_exec.email}"
}
