variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "eu-central-1" # Frankfurt
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "provider-comparison"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "google_maps_api_key" {
  description = "API key for Google Maps service"
  type        = string
  sensitive   = true  # Markiert als sensibel, nicht in Logs anzeigen
  default     = ""
}

# Provider API Keys for Secrets Manager
variable "byteme_api_key" {
  description = "API key for ByteMe provider"
  type        = string
  sensitive   = true
  default     = ""
}

variable "servus_speed_auth" {
  description = "Authorization header for Servus Speed (Basic auth)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "webwunder_api_key" {
  description = "API key for WebWunder provider"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ping_perfect_client_id" {
  description = "Client ID for Ping Perfect"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ping_perfect_secret" {
  description = "Secret for Ping Perfect HMAC signing"
  type        = string
  sensitive   = true
  default     = ""
}

variable "verbyndich_api_key" {
  description = "API key for VerbynDich provider"
  type        = string
  sensitive   = true
  default     = ""
}