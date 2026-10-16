# Global external Application Load Balancer for the public site: serverless NEG
# -> Cloud Run, Cloud CDN for static content, Certificate Manager cert issued via
# DNS authorization (so it is ACTIVE before DNS is cut over), HTTP -> HTTPS.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.20"
    }
  }
}

variable "project_id" {
  type = string
}

variable "name" {
  description = "Resource prefix, e.g. hl-prod."
  type        = string
}

variable "domains" {
  type = list(string)
}

variable "backends" {
  description = "Cloud Run services to route to, keyed by region. One region today; add us-east1 here for DR."
  type        = map(string)
}

resource "google_project_service" "certificatemanager" {
  project            = var.project_id
  service            = "certificatemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_compute_global_address" "lb" {
  project = var.project_id
  name    = "${var.name}-lb-ip"
}

resource "google_compute_region_network_endpoint_group" "run" {
  for_each              = var.backends
  project               = var.project_id
  name                  = "${var.name}-neg-${each.key}"
  region                = each.key
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = each.value
  }
}

resource "google_compute_backend_service" "web" {
  project               = var.project_id
  name                  = "${var.name}-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"
  enable_cdn            = true

  # Only static content types (and responses explicitly marked public) are
  # cached; Django HTML pages are not.
  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    client_ttl        = 3600
    max_ttl           = 86400
    serve_while_stale = 86400
    cache_key_policy {
      include_host         = true
      include_protocol     = true
      include_query_string = true
    }
  }

  dynamic "backend" {
    for_each = google_compute_region_network_endpoint_group.run
    content {
      group = backend.value.id
    }
  }
}

resource "google_compute_url_map" "https" {
  project         = var.project_id
  name            = "${var.name}-url-map"
  default_service = google_compute_backend_service.web.id
}

resource "google_compute_url_map" "http_redirect" {
  project = var.project_id
  name    = "${var.name}-http-redirect"
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_certificate_manager_dns_authorization" "domain" {
  for_each   = toset(var.domains)
  project    = var.project_id
  name       = "${replace(each.value, ".", "-")}-auth"
  domain     = each.value
  depends_on = [google_project_service.certificatemanager]
}

resource "google_certificate_manager_certificate" "site" {
  project = var.project_id
  name    = "${var.name}-cert"
  managed {
    domains            = var.domains
    dns_authorizations = [for a in google_certificate_manager_dns_authorization.domain : a.id]
  }
}

resource "google_certificate_manager_certificate_map" "site" {
  project    = var.project_id
  name       = "${var.name}-cert-map"
  depends_on = [google_project_service.certificatemanager]
}

resource "google_certificate_manager_certificate_map_entry" "domain" {
  for_each     = toset(var.domains)
  project      = var.project_id
  name         = "${replace(each.value, ".", "-")}-entry"
  map          = google_certificate_manager_certificate_map.site.name
  hostname     = each.value
  certificates = [google_certificate_manager_certificate.site.id]
}

resource "google_compute_target_https_proxy" "https" {
  project         = var.project_id
  name            = "${var.name}-https-proxy"
  url_map         = google_compute_url_map.https.id
  certificate_map = "//certificatemanager.googleapis.com/${google_certificate_manager_certificate_map.site.id}"
}

resource "google_compute_target_http_proxy" "http" {
  project = var.project_id
  name    = "${var.name}-http-proxy"
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "https" {
  project               = var.project_id
  name                  = "${var.name}-https"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb.address
  port_range            = "443"
  target                = google_compute_target_https_proxy.https.id
}

resource "google_compute_global_forwarding_rule" "http" {
  project               = var.project_id
  name                  = "${var.name}-http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb.address
  port_range            = "80"
  target                = google_compute_target_http_proxy.http.id
}

output "ip_address" {
  description = "Point the A records for the domains here at cut-over."
  value       = google_compute_global_address.lb.address
}

output "dns_authorization_records" {
  description = "CNAME records to add in Namecheap before cut-over so the cert can issue."
  value = {
    for d, a in google_certificate_manager_dns_authorization.domain :
    d => a.dns_resource_record[0]
  }
}
