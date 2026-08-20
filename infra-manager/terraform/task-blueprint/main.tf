locals {
  raw_task_slug = trim(replace(lower(var.task_id), "/[^a-z0-9-]/", "-"), "-")
  task_slug     = substr(local.raw_task_slug != "" ? local.raw_task_slug : "data-model-task", 0, 50)
  group_label   = substr(replace(lower(var.group), "/[^a-z0-9_-]/", "_"), 0, 63)

  namespace_name = local.task_slug
  ksa_name       = substr("ksa-${local.task_slug}", 0, 63)
  gsa_account_id = substr("dm-task-${local.task_slug}", 0, 30)
  gke_project_id = var.gke_project_id != "" ? var.gke_project_id : var.target_project_id

  request_user_dataset_role = {
    viewer = "roles/bigquery.dataViewer"
    editor = "roles/bigquery.dataEditor"
    owner  = "roles/bigquery.dataOwner"
  }[lower(var.bigquery_role)]

  common_labels = {
    managed_by = "infra-manager"
    task_id    = substr(replace(local.task_slug, "-", "_"), 0, 63)
    task_group = local.group_label
  }
}

resource "google_bigquery_dataset" "task" {
  project                    = var.target_project_id
  dataset_id                 = var.dataset_id
  friendly_name              = var.task_name
  description                = "Data model workspace dataset for ${var.task_id}"
  location                   = var.bq_location
  delete_contents_on_destroy = true

  labels = local.common_labels
}

resource "google_service_account" "task" {
  project      = var.target_project_id
  account_id   = local.gsa_account_id
  display_name = "Data model task ${var.task_id}"
  description  = "Per-task GSA for Jupyter workload ${var.task_id}"
}

# Jupyter/GSA can create BigQuery jobs but only receives data access to its own dataset.
resource "google_project_iam_member" "gsa_bq_job_user" {
  project = var.target_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.task.email}"
}

resource "google_bigquery_dataset_iam_member" "gsa_dataset_editor" {
  project    = var.target_project_id
  dataset_id = google_bigquery_dataset.task.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.task.email}"
}

# Human identity is not created here. Cloud Identity/Workspace/enterprise IdP owns
# the account lifecycle; Terraform grants the approved user access to this task.
resource "google_bigquery_dataset_iam_member" "request_user_dataset" {
  count = var.request_user != "" ? 1 : 0

  project    = var.target_project_id
  dataset_id = google_bigquery_dataset.task.dataset_id
  role       = local.request_user_dataset_role
  member     = "user:${var.request_user}"
}

resource "google_project_iam_member" "request_user_bq_job_user" {
  count = var.request_user != "" ? 1 : 0

  project = var.target_project_id
  role    = "roles/bigquery.jobUser"
  member  = "user:${var.request_user}"
}

resource "kubernetes_namespace_v1" "task" {
  metadata {
    name = local.namespace_name

    labels = {
      "managed-by" = "infra-manager"
      "task-id"    = local.namespace_name
      "task-group" = local.group_label
    }

    annotations = var.expire_date != "" ? {
      "data-model/expire-date" = var.expire_date
    } : {}
  }
}

resource "kubernetes_resource_quota_v1" "task" {
  metadata {
    name      = "task-quota"
    namespace = kubernetes_namespace_v1.task.metadata[0].name
  }

  spec {
    hard = {
      "requests.cpu"    = var.quota_cpu_requests
      "requests.memory" = var.quota_memory_requests
      "limits.cpu"      = var.quota_cpu_limits
      "limits.memory"   = var.quota_memory_limits
      "pods"            = var.quota_pods
    }
  }
}

resource "kubernetes_service_account_v1" "jupyter" {
  metadata {
    name      = local.ksa_name
    namespace = kubernetes_namespace_v1.task.metadata[0].name

    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.task.email
    }
  }
}

# Link KSA -> GSA without a downloaded service-account key.
resource "google_service_account_iam_member" "workload_identity" {
  service_account_id = google_service_account.task.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.gke_project_id}.svc.id.goog[${kubernetes_namespace_v1.task.metadata[0].name}/${kubernetes_service_account_v1.jupyter.metadata[0].name}]"
}

resource "random_password" "jupyter_token" {
  length  = 32
  special = false
}

resource "kubernetes_secret_v1" "jupyter" {
  metadata {
    name      = "jupyter-auth"
    namespace = kubernetes_namespace_v1.task.metadata[0].name
  }

  data = {
    JUPYTER_TOKEN = random_password.jupyter_token.result
  }

  type = "Opaque"
}

resource "kubernetes_persistent_volume_claim_v1" "jupyter" {
  metadata {
    name      = "jupyter-workspace"
    namespace = kubernetes_namespace_v1.task.metadata[0].name
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = var.storage_class_name != "" ? var.storage_class_name : null

    resources {
      requests = {
        storage = var.storage_size
      }
    }
  }
}

resource "kubernetes_deployment_v1" "jupyter" {
  metadata {
    name      = "jupyter"
    namespace = kubernetes_namespace_v1.task.metadata[0].name
    labels = {
      app = "jupyter"
    }
  }

  spec {
    replicas = 1

    strategy {
      type = "Recreate"
    }

    selector {
      match_labels = {
        app = "jupyter"
      }
    }

    template {
      metadata {
        labels = {
          app       = "jupyter"
          "task-id" = local.namespace_name
        }
      }

      spec {
        service_account_name = kubernetes_service_account_v1.jupyter.metadata[0].name

        security_context {
          fs_group = 100
        }

        container {
          name  = "jupyter"
          image = var.jupyter_image

          port {
            name           = "http"
            container_port = 8888
          }

          env {
            name = "JUPYTER_TOKEN"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.jupyter.metadata[0].name
                key  = "JUPYTER_TOKEN"
              }
            }
          }

          resources {
            requests = {
              cpu    = var.jupyter_cpu_request
              memory = var.jupyter_memory_request
            }
            limits = {
              cpu    = var.jupyter_cpu_limit
              memory = var.jupyter_memory_limit
            }
          }

          volume_mount {
            name       = "workspace"
            mount_path = "/home/jovyan/work"
          }

          readiness_probe {
            http_get {
              path = "/api"
              port = 8888
            }
            initial_delay_seconds = 15
            period_seconds        = 10
          }
        }

        volume {
          name = "workspace"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim_v1.jupyter.metadata[0].name
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_resource_quota_v1.task,
    google_service_account_iam_member.workload_identity
  ]
}

resource "kubernetes_service_v1" "jupyter" {
  metadata {
    name      = "jupyter"
    namespace = kubernetes_namespace_v1.task.metadata[0].name
  }

  spec {
    selector = {
      app = "jupyter"
    }

    port {
      name        = "http"
      port        = 8888
      target_port = 8888
    }

    type = var.jupyter_service_type
  }
}
