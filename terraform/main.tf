provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_compute_network" "vpc" {
  name                    = "underground-gis-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "underground-gis-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
}

resource "google_container_cluster" "gke" {
  name     = "underground-gis-cluster"
  location = var.region

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.subnet.name

  initial_node_count = 1

  node_config {
    machine_type = "e2-medium"
    disk_type    = "pd-standard"
    disk_size_gb = 50
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "underground-gis"
  format        = "DOCKER"
}

resource "google_sql_database_instance" "postgres" {
  name             = "underground-gis-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = "db-f1-micro"
  }

  deletion_protection = false
}

resource "google_sql_database" "gisdb" {
  name     = "gisdb"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "user" {
  name     = "postgres"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}
