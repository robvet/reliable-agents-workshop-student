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
- An Azure Container Registry;
- Container Apps and their environment;
- API Management; and
- Application Insights and Log Analytics.

Two dependencies sit **outside** this configuration and must already exist:

- The **PostgreSQL server**. Terraform takes its connection string as an input variable, so it cannot create it.
- The **model deployments**. The application reads their endpoints from `.env`.

Confirm with your instructor how you obtain both before you start.

## Prerequisites

Before beginning deployment, confirm that you have:

- Access to the target Azure subscription;
- Permission to provision resources and role assignments;
- Git installed;
- Azure CLI installed;
- Terraform 1.5 or later installed; and
- Access to the main workshop and student repositories.

### Installing Terraform

Terraform is a single binary from HashiCorp. Install it with a package manager:

```bash
# macOS
brew tap hashicorp/tap && brew install hashicorp/tap/terraform

# Windows
winget install HashiCorp.Terraform

# Linux (Debian/Ubuntu) - see the link below for other distributions
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

For manual downloads and other platforms, see [developer.hashicorp.com/terraform/install](https://developer.hashicorp.com/terraform/install).

Confirm the install and sign in to Azure:

```bash
terraform version      # must report 1.5 or later
az login
az account show        # confirm the correct subscription is active
```

> **Note on state:** this configuration uses Terraform's default local state. Your
> infrastructure record lives in `terraform.tfstate` in the Terraform folder on your own
> machine. No storage account or remote backend is required before you begin. Keep that
> file - it is how Terraform knows what it created and how `terraform destroy` cleans up
> afterward. Never commit it; it contains your database connection string.

## Part 1: Clone the workshop repositories

Clone the student repository, which is the starting point for the hands-on labs:

```bash
git clone https://github.com/robvet/reliable-agents-workshop-student.git
cd reliable-agents-workshop-student
```

Your instructor will provide the main workshop repository, which holds the completed reference application and supporting resources.

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

### Supply the required variable values

The configuration needs five values that have no default. Copy the template and fill it in:

```bash
cd infra/reliableagents/terraform
cp terraform.tfvars.example terraform.tfvars
```

Then edit `terraform.tfvars`:

| Variable               | What to supply                                                                                |
| ---------------------- | --------------------------------------------------------------------------------------------- |
| `subscription_id`      | Your subscription: `az account show --query id -o tsv`                                        |
| `acr_name`             | A **globally unique** registry name, 5-50 lowercase alphanumeric characters                   |
| `database_url`         | The Postgres connection string for the workshop database                                      |
| `apim_publisher_name`  | Your organization name, shown on the API Management developer portal                          |
| `apim_publisher_email` | An address that receives API Management service notifications                                 |

Three more variables have defaults you can override: `location` (`swedencentral`), `resource_group_name` (`rg-reliableagents`), and `tags`.

> **Sharing a subscription with other attendees?** Change `resource_group_name` as well.
> The default puts every attendee in the same resource group. `acr_name` must be unique
> across all of Azure, not just your subscription, so add your initials or a number.

`terraform.tfvars` is gitignored. Do not commit it - it holds a live database connection string.

### Run Terraform

```bash
terraform init      # download the azurerm provider
terraform validate  # check the configuration is well-formed
terraform plan      # review what will be created before anything happens
terraform apply     # provision the resources
```

Read the plan output before approving the apply. It is the same habit this workshop
applies to model output: inspect the proposed action, then decide whether it runs.

> **Expect a long wait.** This configuration provisions an API Management instance, which
> commonly takes 30 to 45 minutes. Start the apply before a break.

When the apply completes, record the outputs:

```bash
terraform output
```

> **Terraform does not create everything.** The Postgres server and the model deployments
> are outside this configuration - `database_url` is an input to Terraform, not something
> it produces. Confirm with your instructor how to obtain them before you begin.

## Part 4: Configure and run the application locally

The application reads its configuration from a `.env` file in the repository root. Copy the template:

```bash
cp .env.example .env
```

Fill in the four values that are environment-specific:

| Key                                     | Where it comes from                                    |
| --------------------------------------- | ------------------------------------------------------ |
| `AZURE_OPENAI_ENDPOINT`                 | Your Azure OpenAI resource endpoint                    |
| `MCP_OPENAI_ENDPOINT`                   | The endpoint the MCP NL-2-SQL service calls            |
| `DATABASE_URL`                          | The Postgres connection string                         |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | From the Terraform output, or the Azure portal         |

The remaining keys ship with working defaults: the two model deployment names, `MCP_SERVER_URL`, timeouts, and display flags. Set `SHOW_VERBOSE_ERRORS=True` while working through the labs if you want the real exception text in an error response instead of a generic message.

### Configure the MCP server

The MCP server runs as its own process and reads its own configuration. Copy its template too:

```bash
cp src/mcp_sql/.env.example src/mcp_sql/.env
```

Fill in `DATABASE_URL`, `MCP_OPENAI_ENDPOINT`, and `INFERENCE_LM_DEPLOYMENT`. The remaining keys have defaults, including the `MAX_ROWS` cap applied to every query the server runs.

> Both files are gitignored. Neither should ever be committed - each holds a live database connection string.

### Start the application

Start all three processes from the repository root:

```bash
./start
```

This launches the MCP server, the backend, and the frontend, and opens a browser. Wait for each to report ready:

| Process     | Address                 |
| ----------- | ----------------------- |
| MCP server  | `http://127.0.0.1:8000` |
| Backend API | `http://127.0.0.1:8010` |
| Frontend    | `http://127.0.0.1:5500` |

If a process reports a traceback instead of a ready message, scroll up in the terminal - the error is above the summary.

## Part 5: Verify the workshop environment

Confirm the backend and MCP server are answering:

```bash
curl -s -o /dev/null -w "backend: %{http_code}\n" http://127.0.0.1:8010/prompt-library
curl -s -o /dev/null -w "mcp:     %{http_code}\n" http://127.0.0.1:8000/mcp
```

The backend should return `200`. The MCP server returns `406` to a plain GET, which is
expected - it speaks the MCP protocol, not ordinary HTTP, and a response at all confirms
it is listening.

Then exercise the full pipeline from the UI:

1. Open `http://localhost:5500`.
2. Go to **Command Center** and submit a supported request, such as `What is the status and provide information about XFMR-1000`.
3. Confirm the Execution Trace shows a classified intent, one or more agent steps, and a final answer.
4. Open the **Asset Map** to confirm the database connection is returning rows.
5. Review the request in Application Insights to confirm telemetry is flowing.

A complete answer with a populated Execution Trace means the whole path is working: frontend, backend, model, MCP server, and database.

## Success criteria

The workshop environment is ready when:

- Terraform has provisioned the required Azure infrastructure.
- The frontend, backend, and MCP server run locally.
- All application services report healthy status.
- A known-good request completes successfully through the full application pipeline.
- You can explain the difference between Azure infrastructure and the locally running application.

## Next step

Continue to [Lab 1: Application and Architecture Tour](../02-hands-on-labs/01-application-overview/lab-1-guide.md).
