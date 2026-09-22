resource "azurerm_container_app" "frontend" {
  workload_profile_name        = "Consumption"
  name                         = "ca-frontend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
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

  # nginx (in this container) proxies /chat, /map, etc. through APIM and needs
  # the "frontend" subscription key — injected as an env var, never baked into
  # the image or nginx.conf itself (see src/frontend/nginx.conf + Dockerfile).
  secret {
    name  = "apim-subscription-key"
    value = azurerm_api_management_subscription.frontend.primary_key
  }

  ingress {
    external_enabled = true
    target_port      = 80
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
      name   = "frontend"
      image  = "${azurerm_container_registry.main.login_server}/frontend:v1"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "APIM_SUBSCRIPTION_KEY"
        secret_name = "apim-subscription-key"
      }
    }
  }

  depends_on = [azurerm_role_assignment.acr_pull]

  # CI/CD (deploy-frontend.yml) updates the image to a git-SHA tag via
  # `az containerapp update`. Ignore image drift so `terraform apply`
  # doesn't revert it to :v1.
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }
}

output "frontend_app_fqdn" {
  value = azurerm_container_app.frontend.ingress[0].fqdn
}
