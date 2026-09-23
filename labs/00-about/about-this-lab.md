# Building Reliable Agents and Agentic Solutions

Language models are probabilistic by design. The same request can produce different outputs, and small inconsistencies can compound as work moves through a multi-agent system.

This workshop focuses on the programmatic patterns and engineering best practices that help improve reliability, accuracy, coherence, and consistency when building applications with language models.

## The workshop approach

You will explore and complete a multi-agent application that combines probabilistic model reasoning with deterministic application control. Models interpret language and recommend actions. Programmatic controls validate those recommendations, restrict what may execute, and preserve typed data throughout the workflow.

The goal is not to make model output deterministic. The goal is to build a reliable system around probabilistic models.

## Learning objectives

- Build a multi-agent application with specialized domain agents.
- Separate probabilistic model reasoning from deterministic application control.
- Convert unstructured requests into known intents and typed data.
- Apply validation and authorization before executing model recommendations.
- Use bounded orchestration, explicit stopping conditions, and structured results.
- Test and observe the complete agentic workflow.

## Guiding principles

- **Classify unstructured requests.** Convert user language into a known intent before routing or execution.
- **Use typed inputs and outputs.** Pass validated objects between components instead of free-form text.
- **Template prompts explicitly.** Define the model's task, available context, and expected result.
- **Validate model and tool boundaries.** Check schemas, types, ranges, and permitted values before execution.
- **Restrict available actions.** Allow models to recommend only agents and operations permitted for the request.
- **Keep control flow deterministic.** Application code owns authorization, dispatch, stopping conditions, and failure handling.
- **Make execution observable.** Record the decisions and steps required to test behavior and diagnose failures.

## What you will build

Across the hands-on labs, you will work with the application's core reliability boundaries:

- typed intent classification;
- deterministic routing and agent allow-lists;
- bounded multi-agent orchestration;
- typed requests and results;
- MCP-backed domain data access; and
- deterministic response assembly.

Each pattern places an explicit programmatic boundary around model behavior. Together, these boundaries make the complete system easier to understand, test, operate, and improve.

## Expected outcome

By the end of the workshop, you will be able to identify where probabilistic reasoning is valuable, where deterministic control is required, and how both work together in a reliable agentic solution.
