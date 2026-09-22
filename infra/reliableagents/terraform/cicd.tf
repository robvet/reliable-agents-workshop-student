data "azurerm_client_config" "current" {}

# Dedicated identity for GitHub Actions CI/CD — kept separate from the runtime
# UAMI (id-reliableagents) so deploy rights and app-runtime rights don't mix.
resource "azurerm_user_assigned_identity" "cicd" {
  name                = "id-reliableagents-cicd"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

# Federated credential: lets GitHub Actions (this repo, main branch) obtain an
# Azure token via OIDC — no client secret stored anywhere.
resource "azurerm_federated_identity_credential" "cicd_main" {
  name                      = "github-main"
  user_assigned_identity_id = azurerm_user_assigned_identity.cicd.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  # This repo has GitHub's immutable-ID OIDC subjects enabled, so the presented
  # `sub` embeds the numeric user/repo IDs (robvet=4884576, repo=1348556281).
  # Must match exactly. Immutable IDs survive owner/repo renames.
  subject = "repo:robvet@4884576/reliable-agents-workshop@1348556281:ref:refs/heads/main"
}

# Contributor on the resource group: covers `az acr build` (schedules the ACR
# build task) and `az containerapp update` (rolls a new revision). Scoped to
# this RG only.
resource "azurerm_role_assignment" "cicd_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.cicd.principal_id
}

output "cicd_client_id" {
  value = azurerm_user_assigned_identity.cicd.client_id
}

output "azure_tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "azure_subscription_id" {
  value = data.azurerm_client_config.current.subscription_id
}
