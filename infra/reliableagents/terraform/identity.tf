data "azurerm_cognitive_account" "foundry" {
  name                = "foundry-playground-aif"
  resource_group_name = "rg-foundry-playground"
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-reliableagents"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "foundry_openai_user" {
  scope                = data.azurerm_cognitive_account.foundry.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

output "uami_client_id" {
  value = azurerm_user_assigned_identity.app.client_id
}

output "uami_principal_id" {
  value = azurerm_user_assigned_identity.app.principal_id
}

output "uami_id" {
  value = azurerm_user_assigned_identity.app.id
}
