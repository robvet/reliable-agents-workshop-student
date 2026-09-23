# Workshop Cleanup

## When not using the workshop

To reduce costs between workshop sessions:

- Stop the frontend, backend, and MCP Azure Container Apps.
- Stop the PostgreSQL server if it is dedicated to the workshop and its hosting service supports stopping.
- Restart these services before resuming the workshop.

## When the workshop is complete

1. Save or commit any work you want to keep.
2. Open a terminal in `infra/reliableagents/terraform`.
3. Review the resources that will be removed:

	```bash
	terraform plan -destroy
	```

4. Destroy the Terraform-managed Azure environment:

	```bash
	terraform destroy
	```

5. Confirm that the workshop resource group and its resources have been removed.
6. Remove the GitHub Actions Azure secrets if they are no longer needed.
7. Separately stop or remove the PostgreSQL server and model deployments if they were created for this workshop.

> Terraform does not manage the PostgreSQL server or model deployments used by this application. `terraform destroy` will not remove them.
