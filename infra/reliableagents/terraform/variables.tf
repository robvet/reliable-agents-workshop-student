variable "subscription_id" {
  description = "Azure subscription ID to deploy into."
  type        = string
}

variable "location" {
  description = "Azure region for all ReliableAgents resources."
  type        = string
  default     = "swedencentral"
}

variable "resource_group_name" {
  description = "Resource group that holds the ReliableAgents deployment."
  type        = string
  default     = "rg-reliableagents"
}

variable "acr_name" {
  description = "Globally-unique name for the Azure Container Registry (5-50 lowercase alphanumeric)."
  type        = string
}

variable "database_url" {
  description = "Postgres connection string stored as a Key Vault secret."
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags applied to all ReliableAgents resources."
  type        = map(string)
  default = {
    solution = "ReliableAgents"
    env      = "demo"
  }
}

variable "apim_publisher_name" {
  description = "Publisher/organization name shown on the APIM developer portal."
  type        = string
}

variable "apim_publisher_email" {
  description = "Publisher email address for the APIM instance (receives service notifications)."
  type        = string
}
