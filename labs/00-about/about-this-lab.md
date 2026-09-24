# Building Reliable Agents and Agentic Solutions

Language models are probabilistic by design. The same request can produce different outputs, and small inconsistencies can compound as work moves through a multi-agent system.

This workshop focuses on the programmatic patterns and engineering best practices that help improve reliability, accuracy, coherence, and consistency when building applications with language models.

## The workshop approach

You will explore and complete a multi-agent application that combines probabilistic model reasoning with deterministic application control. Models interpret language, reason, and recommend actions. Programmatic controls validate those recommendations, restrict what may execute, and preserve typed data throughout the workflow.

The goal is not to make model output deterministic. Models built with transformer architectures are probabilistic by design. Instead, the goal is to wrap reliable controls around probabilistic model behavior.

## Learning objectives

In this lab, you will:

- Explore a multi-agent application with specialized domain agents.
- Isolate probabilistic model reasoning from deterministic application control.
- Transform unstructured user text into refined intents and typed data objects.
- Apply control gates before executing model recommendations.
- Implement bounded orchestration and explicit stopping conditions.

## Guiding principles

You will learn patterns and best practices for building reliable agents and agentic applications:

- **Classify unstructured user requests.** Convert user language into a clearly defined intent before routing or execution.
- **Consume typed inputs and outputs.** Pass validated objects between components instead of error-prone free-form text.
- **Require prompt templating.** Reuse prompt patterns with fixed instructions and defined variables.
- **Validate model and tool boundaries.** Enforce schemas, types, ranges, and permitted values before execution.
- **Restrict available actions.** Limit models to agents and operations permitted for the request.
- **Implement deterministic control flow.** Application code controls dispatch, stopping conditions, and failure handling.
- **Make execution observable.** Record decisions and steps throughout each operation.

## What you will build

Across the hands-on labs, you will work with the application's core reliability boundaries:

- Typed intent classification;
- Deterministic routing and agent allow-lists;
- Bounded multi-agent orchestration;
- Typed requests and results;
- MCP-backed domain data access; and
- Structured final response assembly.

Each pattern places an explicit programmatic boundary around model behavior. Together, these boundaries make the complete system easier to understand, test, operate, and improve.

## Expected outcome

By the end of the workshop, you will be able to identify where probabilistic reasoning is valuable, where deterministic control is required, and how both work together in a reliable agentic solution.
