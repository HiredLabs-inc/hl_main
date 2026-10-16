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
    prefix = "prod"
  }
}

provider "google" {
  region = "us-west1"
}

module "env" {
  source = "../../modules/hl-env"

  env        = "prod"
  project_id = "hl-main-prod"

  host_project_id = "vpc-host-prod-yk380-hm150"
  network         = "vpc-prod-shared"
  subnet          = "subnet-prod-1"

  image_repo    = "us-west1-docker.pkg.dev/hl-main-prod/hl-images/hl-main"
  artifact_repo = { project = "hl-main-prod", location = "us-west1", name = "hl-images" }

  web_ingress       = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  web_min_instances = 1 # the Playwright image cold-starts slowly
  web_memory        = "1Gi"
  worker_memory     = "2Gi"

  sql_disk_type              = "PD_SSD"
  sql_always_on              = true
  sql_retained_backups       = 7
  sql_point_in_time_recovery = true
  deletion_protection        = true

  deploy_branch = "main"
}

module "lb" {
  source = "../../modules/hl-lb"

  project_id = "hl-main-prod"
  name       = "hl-prod"
  domains    = ["hiredlabs.org", "www.hiredlabs.org"]
  # DR: add us-east1 = "hl-prod-web" once a us-east1 service exists (docs/runbook).
  backends = { "us-west1" = module.env.web_service_name }

  # module.env enables the project APIs (compute, etc.) the LB needs.
  depends_on = [module.env]
}

output "env" {
  value = module.env
}

output "lb_ip_address" {
  value = module.lb.ip_address
}

output "dns_authorization_records" {
  value = module.lb.dns_authorization_records
}
