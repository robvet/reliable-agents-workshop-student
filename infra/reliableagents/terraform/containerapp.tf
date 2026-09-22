resource "azurerm_container_app_environment" "main" {
  name                       = "cae-reliableagents"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  logs_destination           = "log-analytics"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    minimum_count         = 0
    maximum_count         = 0
  }
}

resource "azurerm_container_app" "mcp" {
  name                         = "ca-mcp-sql"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  # Pull from ACR using the user-assigned identity (AcrPull granted in identity.tf).
  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.app.id
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "mcp-sql"
      image  = "${azurerm_container_registry.main.login_server}/mcp-sql:v1"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "MCP_OPENAI_ENDPOINT"
        value = "https://foundry-playground-aif.services.ai.azure.com/"
      }
      env {
        name  = "INFERENCE_LM_DEPLOYMENT"
        value = "gpt-5.6-sol"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.app.client_id
      }
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }
    }
  }

  depends_on = [azurerm_role_assignment.acr_pull]

  # CI/CD (deploy-mcp.yml) updates the image to a git-SHA tag via
  # `az containerapp update`. Ignore image drift so `terraform apply`
  # doesn't revert it to :v1.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }
}

output "mcp_app_fqdn" {
  value = azurerm_container_app.mcp.ingress[0].fqdn
}
