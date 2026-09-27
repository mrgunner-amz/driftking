# app-stack v2: the "after" infrastructure, planned against v1's state.
#
# Differences from v1, and what Terraform should plan for each:
#   - database engine 15 -> 16 via triggers_replace   => replace
#   - api scaled from 2 to 3 instances                 => create api[2]
#   - api now reads from a new cache                   => create cache, update api
#   - legacy_worker removed from configuration         => delete
#   - network, audit_log_bucket, monitoring unchanged  => no-op
# Everything else Terraform decides for itself (e.g. which resources update
# because an ID they reference becomes unknown).

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
    engine_version = "16"
    subnet         = terraform_data.network.output.cidr
  }

  triggers_replace = {
    engine_version = "16"
  }
}

resource "terraform_data" "cache" {
  input = {
    engine = "redis"
    subnet = terraform_data.network.output.cidr
  }
}

resource "terraform_data" "api" {
  count = 3

  input = {
    image       = "api:1.4.0"
    database_id = terraform_data.database.id
    cache_id    = terraform_data.cache.id
    db_password = var.db_password
  }
}

resource "terraform_data" "load_balancer" {
  input = {
    listener = "https:443"
    targets  = terraform_data.api[*].id
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
