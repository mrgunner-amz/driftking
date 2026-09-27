variable "target_id" {
  description = "ID of the resource to health-check."
  type        = string
}

resource "terraform_data" "health_check" {
  input = {
    target   = var.target_id
    interval = "30s"
  }
}

output "health_check_id" {
  value = terraform_data.health_check.id
}
