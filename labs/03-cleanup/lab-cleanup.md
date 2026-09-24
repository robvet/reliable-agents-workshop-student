# Workshop Cleanup

Stop the workshop's Azure resources between sessions, or remove them and your local configuration entirely when you are finished.

## When not using the workshop

To reduce costs between workshop sessions:

- Stop the frontend, backend, and MCP Azure Container Apps.
- Stop the PostgreSQL server if it is dedicated to the workshop and its hosting service supports stopping.
- Restart these services before resuming the workshop.

## When the workshop is complete

1. Save or commit any work you want to keep.
2. Stop the frontend, backend, and MCP processes.
3. Open a terminal in `infra/reliableagents/terraform`.
4. Review the resources that will be removed:

	```bash
	terraform plan -destroy
	```

5. Destroy the Terraform-managed Azure environment:

	```bash
	terraform destroy
	```

6. Confirm that the workshop resource group and its resources have been removed.
7. Remove the GitHub Actions Azure secrets if they are no longer needed.
8. Separately stop or remove the PostgreSQL server and model deployments if they were created for this workshop.
9. Remove local environment files and temporary credentials if you no longer need them.

> Terraform does not manage the PostgreSQL server or model deployments used by this application. `terraform destroy` will not remove them.

## Confirm cleanup

- No workshop processes remain running.
- No unintended billable Azure resources remain deployed.
- Local credentials and environment files are removed or intentionally retained.
- Your source changes are committed or intentionally discarded.
