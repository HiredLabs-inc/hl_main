terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.20"
    }
  }
  backend "gcs" {
    bucket = "hiredlabs-tf-state"
    prefix = "stage"
  }
}

provider "google" {
  region = "us-west1"
}

module "env" {
  source = "../../modules/hl-env"

  env        = "stage"
  project_id = "hl-main-stage"

  host_project_id = "vpc-host-staging-yk380-hm150"
  network         = "vpc-staging-shared"
  subnet          = "subnet-staging-1"

  image_repo    = "us-west1-docker.pkg.dev/hl-main-prod/hl-images/hl-main"
  artifact_repo = { project = "hl-main-prod", location = "us-west1", name = "hl-images" }

  web_ingress       = "INGRESS_TRAFFIC_ALL" # served on its run.app URL
  web_min_instances = 0
  web_memory        = "1Gi"
  worker_memory     = "1Gi"

  # Stopped unless someone is testing: ~$1/mo stopped.
  sql_disk_type              = "PD_HDD"
  sql_always_on              = false
  sql_nightly_stop           = true
  sql_retained_backups       = 1
  sql_point_in_time_recovery = false
  deletion_protection        = false

  deploy_branch = "staging"
}

output "env" {
  value = module.env
}
