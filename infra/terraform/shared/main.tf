# Cross-environment resources: Shared VPC attachments, private services access
# for Cloud SQL in the prod network, and the single Artifact Registry repo.
# Apply this before envs/stage and envs/prod.

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
    prefix = "shared"
  }
}

provider "google" {
  region = "us-west1"
}

# The Org Policy API needs an explicit quota project when Terraform runs with
# user Application Default Credentials.
provider "google" {
  alias                 = "quota"
  region                = "us-west1"
  billing_project       = "hl-main-stage"
  user_project_override = true
}

locals {
  region = "us-west1"
  hosts = {
    prod  = { project = "vpc-host-prod-yk380-hm150", network = "vpc-prod-shared", service_project = "hl-main-prod" }
    stage = { project = "vpc-host-staging-yk380-hm150", network = "vpc-staging-shared", service_project = "hl-main-stage" }
  }
}

# The public web services use invoker_iam_disabled (no allUsers binding, so
# domain-restricted sharing stays on). That requires relaxing this managed
# constraint on the environment projects.
resource "google_project_service" "env_orgpolicy" {
  for_each           = local.hosts
  project            = each.value.service_project
  service            = "orgpolicy.googleapis.com"
  disable_on_destroy = false
}

resource "google_org_policy_policy" "allow_invoker_iam_disabled" {
  provider = google.quota
  for_each = local.hosts
  name     = "projects/${each.value.service_project}/policies/run.managed.requireInvokerIam"
  parent   = "projects/${each.value.service_project}"
  spec {
    rules {
      enforce = "FALSE"
    }
  }
  depends_on = [google_project_service.env_orgpolicy]
}

# Set by hand on stage during the first apply (2026-10-14).
import {
  to = google_org_policy_policy.allow_invoker_iam_disabled["stage"]
  id = "projects/hl-main-stage/policies/run.managed.requireInvokerIam"
}

resource "google_compute_shared_vpc_service_project" "env" {
  for_each        = local.hosts
  host_project    = each.value.project
  service_project = each.value.service_project
}

# Private services access for Cloud SQL in the prod network. (The staging
# network already has a peering on range "sql-dev", 10.0.32.0/20, which the new
# stage instance reuses.)
resource "google_project_service" "prod_host_servicenetworking" {
  project            = local.hosts.prod.project
  service            = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

resource "google_compute_global_address" "prod_sql_range" {
  project       = local.hosts.prod.project
  name          = "sql-prod"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  address       = "10.0.64.0"
  prefix_length = 20
  network       = "projects/${local.hosts.prod.project}/global/networks/${local.hosts.prod.network}"
}

resource "google_service_networking_connection" "prod_sql" {
  network                 = "projects/${local.hosts.prod.project}/global/networks/${local.hosts.prod.network}"
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.prod_sql_range.name]
  depends_on              = [google_project_service.prod_host_servicenetworking]
}

# One image repo for both environments.
resource "google_project_service" "prod_artifactregistry" {
  project            = "hl-main-prod"
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "images" {
  project       = "hl-main-prod"
  location      = local.region
  repository_id = "hl-images"
  format        = "DOCKER"
  description   = "hl_main images (built by Cloud Build in stage and prod)"

  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
  cleanup_policies {
    id     = "keep-env-tags"
    action = "KEEP"
    condition {
      tag_state    = "TAGGED"
      tag_prefixes = ["prod", "stage", "fallback"]
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.prod_artifactregistry]
}

output "image_repo" {
  value = "${local.region}-docker.pkg.dev/hl-main-prod/${google_artifact_registry_repository.images.repository_id}/hl-main"
}
