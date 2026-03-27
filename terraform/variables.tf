variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "backend_image_tag" {
  description = "Docker image tag for the backend"
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Docker image tag for the frontend"
  type        = string
  default     = "latest"
}

variable "github_token" {
  description = "GitHub token for Gist publishing (optional)"
  type        = string
  default     = ""
  sensitive   = true
}
