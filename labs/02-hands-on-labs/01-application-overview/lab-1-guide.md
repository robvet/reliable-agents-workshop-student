# Lab 1: Application and Architecture Tour

## Introduction

This instructor-led lab is a hands-on tour of the application and its code. The instructor will guide the class through each activity while students run the same steps on their own computers.

Together, you will explore the user experience, operational use case, architecture, data, tests, and key application scenarios. You will also examine the critical code paths that combine model-driven reasoning with deterministic engineering controls to improve agent and agentic-system reliability.

## Lab format

This lab is completed as a team:

1. The instructor introduces each area of the application.
2. The instructor demonstrates an activity or code path.
3. Students mirror the activity in their local environment.
4. The class discusses what happened and where reliability controls are applied.

No code changes are required in this lab.

## Learning objectives

By the end of this lab, you will be able to:

- Explain the application's operational use case and user experience.
- Describe the major architecture components and their responsibilities.
- Follow a request through classification, reasoning, dispatch, data access, and response assembly.
- Identify the application's core data and how agents access it.
- Run the tests and explain what key behaviors they verify.
- Recognize where deterministic engineering controls constrain and validate model behavior.

## Guided tour

### 1. Explore the application

Review each area of the user interface and identify how a user submits a request, follows its execution, and receives the final response.

### 2. Understand the use case

Discuss the asset-event response scenario, the operational questions the application answers, and the roles of the specialized domain agents.

### 3. Review the architecture

Walk through the end-to-end request path from the user prompt to the rendered answer. Identify the model calls, typed boundaries, deterministic control points, domain agents, and data-access path.

### 4. Explore the data

Review the application's core data and relationships. Follow one agent request through the MCP and natural-language-to-SQL read path.

### 5. Run the tests

Run the focused test suites and review the behaviors they protect. Connect each test to the application component and reliability principle it verifies.

### 6. Run key scenarios

Submit representative prompts and follow each request through the Execution Trace. Predict the expected intent and permitted agents before reviewing the result.

### 7. Walk through critical code

As a class, inspect the code that implements:

- typed intent classification;
- deterministic routing and agent allow-lists;
- reliable orchestration and stopping conditions;
- typed requests and results;
- MCP-backed data access; and
- deterministic response assembly.

For each code path, identify what the model proposes, what deterministic code validates or controls, and how that boundary improves reliability.

## Success criteria

You have completed this lab when you have a comprehensive understanding of:

- the application's purpose and user experience;
- the architecture and end-to-end request path;
- the core data and agent data-access flow;
- the role of the test suite; and
- where the application uses deterministic engineering principles to improve agent and agentic-system reliability.

## Code changes

None. This is an instructor-led application and architecture tour.
