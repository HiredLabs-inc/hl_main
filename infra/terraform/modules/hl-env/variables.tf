variable "env" {
  description = "Environment name: stage or prod. Used as the hl-<env>-* resource prefix."
  type        = string
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-west1"
}

# --- Shared VPC -------------------------------------------------------------

variable "host_project_id" {
  description = "Shared VPC host project."
  type        = string
}

variable "network" {
  description = "Shared VPC network name in the host project."
  type        = string
}

variable "subnet" {
  description = "Subnet (in var.region) used for Cloud Run Direct VPC egress."
  type        = string
}

# --- Cloud Run --------------------------------------------------------------

variable "image_repo" {
  description = "Artifact Registry image path without tag, e.g. us-west1-docker.pkg.dev/hl-main-prod/hl-images/hl-main."
  type        = string
}

variable "artifact_repo" {
  description = "Artifact Registry repository the image lives in."
  type = object({
    project  = string
    location = string
    name     = string
  })
}

variable "web_ingress" {
  description = "INGRESS_TRAFFIC_ALL or INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER."
  type        = string
}

variable "web_min_instances" {
  type = number
}

variable "web_max_instances" {
  type    = number
  default = 10
}

variable "web_memory" {
  type    = string
  default = "1Gi"
}

variable "worker_memory" {
  type    = string
  default = "2Gi"
}

# --- Cloud SQL --------------------------------------------------------------

variable "sql_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "sql_disk_type" {
  description = "PD_SSD or PD_HDD. Cannot be changed after creation."
  type        = string
}

variable "sql_always_on" {
  description = "false: deploys start the instance (and the deploy SA may do so); combine with sql_nightly_stop to keep it off when idle."
  type        = bool
}

variable "sql_retained_backups" {
  type = number
}

variable "sql_point_in_time_recovery" {
  type = bool
}

variable "sql_nightly_stop" {
  description = "Cloud Scheduler job that stops the instance every night."
  type        = bool
  default     = false
}

variable "signup_reminders_schedule" {
  description = "Cron schedule (America/Los_Angeles) that runs the signup-reminders job; null runs it only by hand."
  type        = string
  default     = null
}

variable "deletion_protection" {
  type = bool
}

# --- CI/CD ------------------------------------------------------------------

variable "github_owner" {
  type    = string
  default = "HiredLabs-inc"
}

variable "github_repo" {
  type    = string
  default = "hl_main"
}

variable "deploy_branch" {
  description = "Pushes to this branch build and deploy this environment."
  type        = string
}
