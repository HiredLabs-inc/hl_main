# One hl_main environment (stage or prod) in its own project, attached to a
# Shared VPC. Cloud Build owns the container image; Terraform owns everything else.

locals {
  name = "hl-${var.env}"
  apis = [
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudtasks.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
  ]
  # Deployed until the first Cloud Build run replaces it.
  placeholder_image = "us-docker.pkg.dev/cloudrun/container/hello"

  network_id   = "projects/${var.host_project_id}/global/networks/${var.network}"
  subnet_id    = "projects/${var.host_project_id}/regions/${var.region}/subnetworks/${var.subnet}"
  run_agent    = "service-${data.google_project.this.number}@serverless-robot-prod.iam.gserviceaccount.com"
  secret_name  = "${local.name}-app-env"
  sql_instance = "${local.name}-sql"
  container_env = {
    DJANGO_SETTINGS_MODULE = "hl_main.settings.cloud"
    GCP_PROJECT_ID         = var.project_id
    GCP_SECRETS_NAME       = local.secret_name
  }
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# --- Service accounts (no keys) ---------------------------------------------

resource "google_service_account" "app" {
  project      = var.project_id
  account_id   = "${local.name}-app"
  display_name = "hl_main ${var.env} runtime (web, worker, jobs)"
}

resource "google_service_account" "deploy" {
  project      = var.project_id
  account_id   = "${local.name}-deploy"
  display_name = "hl_main ${var.env} Cloud Build deployer"
}

resource "google_project_iam_member" "app" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/cloudtasks.enqueuer",
  ])
  project = var.project_id
  role    = each.value
  member  = google_service_account.app.member
}

# The app mints Cloud Tasks OIDC tokens as itself (serviceAccountUser) and signs
# GCS URLs through IAM signBlob (serviceAccountTokenCreator); see hl_main/gcs.py.
resource "google_service_account_iam_member" "app_self" {
  for_each = toset([
    "roles/iam.serviceAccountTokenCreator",
    "roles/iam.serviceAccountUser",
  ])
  service_account_id = google_service_account.app.name
  role               = each.value
  member             = google_service_account.app.member
}

resource "google_project_iam_member" "deploy" {
  for_each = toset(concat(
    ["roles/run.developer", "roles/logging.logWriter"],
    # Stage deploys start the stopped-by-default database before migrating.
    var.sql_always_on ? [] : ["roles/cloudsql.editor"],
  ))
  project = var.project_id
  role    = each.value
  member  = google_service_account.deploy.member
}

resource "google_service_account_iam_member" "deploy_acts_as_app" {
  service_account_id = google_service_account.app.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deploy.member
}

resource "google_artifact_registry_repository_iam_member" "deploy_writer" {
  project    = var.artifact_repo.project
  location   = var.artifact_repo.location
  repository = var.artifact_repo.name
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.deploy.member
}

resource "google_artifact_registry_repository_iam_member" "run_agent_reader" {
  project    = var.artifact_repo.project
  location   = var.artifact_repo.location
  repository = var.artifact_repo.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${local.run_agent}"
  depends_on = [google_project_service.apis]
}

# Direct VPC egress into the Shared VPC subnet.
resource "google_compute_subnetwork_iam_member" "network_user" {
  for_each = {
    run_agent = "serviceAccount:${local.run_agent}"
    deploy    = google_service_account.deploy.member
  }
  project    = var.host_project_id
  region     = var.region
  subnetwork = var.subnet
  role       = "roles/compute.networkUser"
  member     = each.value
  depends_on = [google_project_service.apis]
}

# --- Secrets, storage, queue ------------------------------------------------

# Container only. The value is the .env blob read by hl_main/settings/cloud.py,
# added out-of-band so no secret ends up in Terraform state:
#   gcloud secrets versions add hl-<env>-app-env --data-file=.env --project=<project>
resource "google_secret_manager_secret" "app_env" {
  project   = var.project_id
  secret_id = local.secret_name
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "app_env" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.app_env.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.app.member
}

resource "google_storage_bucket" "media" {
  project                     = var.project_id
  name                        = "hiredlabs-${var.env}-media"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
}

resource "google_storage_bucket_iam_member" "media" {
  bucket = google_storage_bucket.media.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.app.member
}

resource "google_cloud_tasks_queue" "tasks" {
  project    = var.project_id
  name       = "${local.name}-tasks"
  location   = var.region
  depends_on = [google_project_service.apis]
}

# --- Cloud SQL --------------------------------------------------------------

resource "google_sql_database_instance" "db" {
  project             = var.project_id
  name                = local.sql_instance
  region              = var.region
  database_version    = "POSTGRES_15"
  deletion_protection = var.deletion_protection

  settings {
    tier                        = var.sql_tier
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL"
    disk_type                   = var.sql_disk_type
    disk_size                   = 10
    disk_autoresize             = true
    # Always created running (the database and user can't be created on a
    # stopped instance). Instances with sql_always_on = false are then stopped
    # by the nightly scheduler job and started by stage deploys.
    activation_policy           = "ALWAYS"
    deletion_protection_enabled = var.deletion_protection

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = local.network_id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "08:00"
      point_in_time_recovery_enabled = var.sql_point_in_time_recovery
      transaction_log_retention_days = var.sql_point_in_time_recovery ? 7 : 1
      backup_retention_settings {
        retained_backups = var.sql_retained_backups
      }
    }

    # Sunday 03:00 Pacific
    maintenance_window {
      day  = 7
      hour = 10
    }
  }

  lifecycle {
    # Stage is started/stopped outside Terraform (deploys, scheduler, by hand).
    ignore_changes = [settings[0].activation_policy]
  }

  depends_on = [google_project_service.apis]
}

# The DB user is created out-of-band so its password stays out of state:
#   gcloud sql users create hiredlabs --instance=hl-<env>-sql --password=... --project=<project>
resource "google_sql_database" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.db.name
  name     = "hiredlabs"
}

# Nightly stop for databases that should only run while someone is testing.
resource "google_service_account" "sql_scheduler" {
  count        = var.sql_nightly_stop ? 1 : 0
  project      = var.project_id
  account_id   = "${local.name}-sql-scheduler"
  display_name = "Stops ${local.sql_instance} nightly"
}

resource "google_project_iam_member" "sql_scheduler" {
  count   = var.sql_nightly_stop ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.editor"
  member  = google_service_account.sql_scheduler[0].member
}

resource "google_cloud_scheduler_job" "sql_nightly_stop" {
  count     = var.sql_nightly_stop ? 1 : 0
  project   = var.project_id
  region    = var.region
  name      = "${local.sql_instance}-nightly-stop"
  schedule  = "0 2 * * *"
  time_zone = "America/Los_Angeles"

  http_target {
    http_method = "PATCH"
    uri         = "https://sqladmin.googleapis.com/v1/projects/${var.project_id}/instances/${local.sql_instance}"
    body        = base64encode(jsonencode({ settings = { activationPolicy = "NEVER" } }))
    headers     = { "Content-Type" = "application/json" }
    oauth_token {
      service_account_email = google_service_account.sql_scheduler[0].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_project_service.apis]
}

# --- Cloud Run --------------------------------------------------------------

resource "google_cloud_run_v2_service" "web" {
  project              = var.project_id
  name                 = "${local.name}-web"
  location             = var.region
  ingress              = var.web_ingress
  invoker_iam_disabled = true # public site without an allUsers binding (keeps domain-restricted sharing on)
  deletion_protection  = var.deletion_protection

  template {
    service_account                  = google_service_account.app.email
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = var.web_min_instances
      max_instance_count = var.web_max_instances
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = local.network_id
        subnetwork = local.subnet_id
      }
    }

    containers {
      image = local.placeholder_image
      resources {
        limits            = { cpu = "1", memory = var.web_memory }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = local.container_env
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  lifecycle {
    # scaling: service-level block the API echoes back empty (scaling lives in template).
    ignore_changes = [template[0].containers[0].image, client, client_version, scaling]
  }

  depends_on = [google_project_service.apis, google_compute_subnetwork_iam_member.network_user]
}

resource "google_cloud_run_v2_service" "worker" {
  project             = var.project_id
  name                = "${local.name}-worker"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY" # Cloud Tasks in the same project counts as internal
  deletion_protection = var.deletion_protection

  template {
    service_account                  = google_service_account.app.email
    timeout                          = "900s"
    max_instance_request_concurrency = 10

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = local.network_id
        subnetwork = local.subnet_id
      }
    }

    containers {
      image = local.placeholder_image
      resources {
        limits            = { cpu = "1", memory = var.worker_memory }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = merge(local.container_env, { DJANGO_ROLE = "worker" })
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  lifecycle {
    # scaling: service-level block the API echoes back empty (scaling lives in template).
    ignore_changes = [template[0].containers[0].image, client, client_version, scaling]
  }

  depends_on = [google_project_service.apis, google_compute_subnetwork_iam_member.network_user]
}

# Cloud Tasks calls the worker with an OIDC token for the app service account.
resource "google_cloud_run_v2_service_iam_member" "worker_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.worker.name
  role     = "roles/run.invoker"
  member   = google_service_account.app.member
}

# hl-<env>-migrate runs on every deploy. hl-<env>-manage runs any management
# command on demand, e.g.:
#   gcloud run jobs execute hl-stage-manage --region=us-west1 --args=manage.py,loaddata,skills
resource "google_cloud_run_v2_job" "jobs" {
  for_each = {
    migrate = ["sh", "-c", "python manage.py migrate --no-input && python manage.py createcachetable"]
    manage  = ["python", "manage.py", "showmigrations"]
  }
  project             = var.project_id
  name                = "${local.name}-${each.key}"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.app.email
      max_retries     = 0
      timeout         = "1200s"

      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = local.network_id
          subnetwork = local.subnet_id
        }
      }

      containers {
        image   = local.placeholder_image
        command = [each.value[0]]
        args    = slice(each.value, 1, length(each.value))
        resources {
          limits = { cpu = "1", memory = "1Gi" }
        }
        dynamic "env" {
          for_each = local.container_env
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_service.apis, google_compute_subnetwork_iam_member.network_user]
}

# --- CI/CD ------------------------------------------------------------------

# Requires the Cloud Build GitHub App to be installed on the repo and the repo
# connected to this project (one-time, in the console).
resource "google_cloudbuild_trigger" "deploy" {
  project         = var.project_id
  location        = "global"
  name            = "${local.name}-deploy"
  description     = "Push to ${var.deploy_branch}: build, migrate and deploy ${var.env}"
  filename        = "infra/cloudbuild/deploy.yaml"
  service_account = google_service_account.deploy.id
  ignored_files   = ["infra/terraform/**", "**/*.md"]

  github {
    owner = var.github_owner
    name  = var.github_repo
    push {
      branch = "^${var.deploy_branch}$"
    }
  }

  substitutions = {
    _ENV       = var.env
    _REGION    = var.region
    _IMAGE     = var.image_repo
    _START_SQL = var.sql_always_on ? "false" : "true"
  }

  depends_on = [google_project_service.apis]
}
