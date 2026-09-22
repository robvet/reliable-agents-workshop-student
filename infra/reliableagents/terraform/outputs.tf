output "resource_group_name" {
  description = "Resource group holding the ReliableAgents deployment."
  value       = azurerm_resource_group.main.name
}

output "acr_name" {
  description = "Azure Container Registry name."
  value       = azurerm_container_registry.main.name
}

output "acr_login_server" {
  description = "ACR login server (used for docker/az acr build image tags)."
  value       = azurerm_container_registry.main.login_server
}
