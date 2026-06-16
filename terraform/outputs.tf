output "gke_cluster_name" {
  value = google_container_cluster.gke.name
}

output "db_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "artifact_registry_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/underground-gis"
}