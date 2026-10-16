output "app_service_account" {
  value = google_service_account.app.email
}

output "web_service_name" {
  value = google_cloud_run_v2_service.web.name
}

output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "worker_url" {
  value = google_cloud_run_v2_service.worker.uri
}

output "sql_instance" {
  value = google_sql_database_instance.db.name
}

output "sql_private_ip" {
  value = google_sql_database_instance.db.private_ip_address
}

output "media_bucket" {
  value = google_storage_bucket.media.name
}

output "task_queue" {
  value = google_cloud_tasks_queue.tasks.name
}

output "secret_name" {
  value = google_secret_manager_secret.app_env.secret_id
}
