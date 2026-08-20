variable "project_id" {
  description = "Platform project ID"
  type        = string
  default     = "dev-com-334508"
}

variable "im_exec_account_id" {
  description = "Infrastructure Manager execution service account ID"
  type        = string
  default     = "infra-manager-exec"
}

variable "adapter_account_id" {
  description = "Cloud Run adapter service account ID"
  type        = string
  default     = "infra-adapter"
}
