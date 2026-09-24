# Workshop Deployment

## Introduction

Workshop participants clone the main workshop repository and the student repository, provision the required Azure infrastructure with Terraform, and run the application locally.

Terraform provisions the Azure infrastructure, identities, permissions, and service configuration required by the workshop application. Configuring CI/CD is not required to complete the labs.

In this section, you will prepare the workshop environment and verify that the application works end to end before beginning the hands-on labs.

## Learning objectives

By the end of this section, you will be able to:

- Describe the application's Azure architecture.
- Explain which resources Terraform creates and manages.
- Clone the workshop repositories.
- Run the application locally.
- Verify the health and connectivity of the application.

## Deployment approach

The workshop uses Terraform to provision the Azure resources required by the application. The frontend, backend, and MCP server run locally during the hands-on labs and connect to those Azure resources.

Terraform provisions and configures:

- An Azure resource group;
- Managed identities and role assignments;
- Application Insights and Log Analytics;
- Connections to the workshop's model deployments; and
- The PostgreSQL database used by the application.

## Prerequisites

Before beginning deployment, confirm that you have:

- Access to the target Azure subscription;
- Permission to provision resources and role assignments;
- Git installed;
- Azure CLI installed;
- Terraform installed; and
- Access to the main workshop and student repositories.

_Installation links, version requirements, and environment checks will be added during the deployment walkthrough._

## Part 1: Clone the workshop repositories

Clone the main workshop repository and the student repository to your computer. The main repository provides the completed reference application and supporting workshop resources. The student repository provides the starting point for the hands-on labs.

_Repository links, clone commands, and the expected local folder structure will be added during the deployment walkthrough._

## Part 2: Review the Terraform configuration

The Terraform configuration is located in `infra/reliableagents/terraform`.

Review how the configuration defines:

1. Resource naming, region, tags, and input variables.
2. Azure resources used by the workshop application.
3. Managed identities and role assignments.
4. Application Insights and Log Analytics.
5. Connections to the model deployments and PostgreSQL database.
6. Outputs used to configure the local application.

## Part 3: Provision the Azure infrastructure

Use Terraform to initialize the working directory, validate the configuration, review the deployment plan, and provision the Azure resources.

_The exact Terraform commands, required variable values, and expected outputs will be added after the deployment configuration is finalized._

## Part 4: Configure and run the application locally

Use the Terraform outputs to configure the local application. Start the frontend, backend, and MCP server from the student repository.

_The exact configuration values, startup commands, and expected terminal output will be added during the deployment walkthrough._

## Part 5: Verify the workshop environment

After the Azure resources are provisioned and the local services are running:

1. Open the local frontend.
2. Verify connectivity between the frontend, backend, MCP server, models, and database.
3. Submit a known-good request.
4. Confirm that the response includes an intent, execution steps, and a final answer.
5. Review the application telemetry for the request.

_Exact verification commands and expected results will be added during the deployment walkthrough._

## Success criteria

The workshop environment is ready when:

- Terraform has provisioned the required Azure infrastructure.
- The frontend, backend, and MCP server run locally.
- All application services report healthy status.
- A known-good request completes successfully through the full application pipeline.
- You can explain the difference between Azure infrastructure and the locally running application.

## Next step

Continue to [Lab 1: Application and Architecture Tour](../02-hands-on-labs/01-application-overview/lab-1-guide.md).
