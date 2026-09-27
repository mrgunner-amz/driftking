# app-stack v1: the "before" infrastructure.
#
# Uses only Terraform's built-in terraform_data resource, so plans can be
# generated with no cloud provider, credentials or provider downloads.

terraform {
  required_version = ">= 1.4"
}

variable "db_password" {
  description = "Placeholder used to exercise sensitive-value handling. Not a real secret."
  type        = string
  sensitive   = true
  default     = "example-not-a-real-secret"
}

resource "terraform_data" "network" {
  input = {
    cidr = "10.0.0.0/16"
  }
}

resource "terraform_data" "database" {
  input = {
    engine         = "postgres"
    engine_version = "15"
    subnet         = terraform_data.network.output.cidr
  }

  # Changing the major version forces a new database, as it would for a
  # real managed database.
  triggers_replace = {
    engine_version = "15"
  }
}

resource "terraform_data" "api" {
  count = 2

  input = {
    image       = "api:1.4.0"
    database_id = terraform_data.database.id
    db_password = var.db_password
  }
}

resource "terraform_data" "load_balancer" {
  input = {
    listener = "https:443"
    targets  = terraform_data.api[*].id
  }
}

resource "terraform_data" "legacy_worker" {
  input = {
    image       = "worker:0.9.2"
    database_id = terraform_data.database.id
  }
}

resource "terraform_data" "audit_log_bucket" {
  input = {
    retention_days = 365
  }
}

module "monitoring" {
  source    = "../modules/monitoring"
  target_id = terraform_data.load_balancer.id
}
