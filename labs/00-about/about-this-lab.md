# Building Reliable Agents and Agentic Solutions

Language models are probabilistic by design. The same request can produce different outputs, and small inconsistencies compound as work moves through a multi-agent system.

This workshop is about the engineering practices that make such a system dependable anyway. You will deploy, explore, and complete a multi-agent application that answers operational questions about electric-grid assets, outages, and crews - the kind of system where a confidently wrong answer has consequences.

## Deterministic engineering

The goal is not to make model output deterministic. Transformer-based models are probabilistic by design, and that is precisely what makes them useful for interpreting language. The goal is to wrap deterministic controls around that behavior, separating what the model **proposes** from what the application **permits**.

This workshop calls that discipline _deterministic engineering_, and you will meet it as a recurring callout in every lab, marking the specific decision that keeps a probabilistic component inside a predictable system. The division of labor is consistent:

| The model                        | The application                         |
| -------------------------------- | --------------------------------------- |
| Interprets the user's language   | Validates that interpretation           |
| Recommends which agent runs next | Decides whether that agent is permitted |
| Generates a database query       | Constrains, authorizes, and executes it |
| Claims the work is finished      | Decides when the loop actually stops    |

Read the right-hand column again. None of it asks the model to behave. Each control makes misbehavior either impossible or visible.

## Why a multi-agent architecture

A single agent holding every tool and every domain rule is simpler, and for a small tool surface it is often the right answer. As that surface grows, the model has more room to choose wrong, and there is no natural place to say "this request may use these capabilities and not those."

This application answers questions spanning assets, events, outages, crews, reliability, and weather. Those domains have different data paths, different rules, and different permissions - so the work is split across specialist agents, with a deterministic router in front of them. Each intent permits a specific set of agents, enforced by a lookup that runs before anything executes.

## Guiding principles

Seven patterns recur throughout the labs:

- **Classify unstructured user requests.** Convert user language into a clearly defined intent before routing or execution.
- **Consume typed inputs and outputs.** Pass validated objects between components instead of error-prone free-form text.
- **Require prompt templating.** Reuse prompt patterns with fixed instructions and defined variables.
- **Validate model and tool boundaries.** Enforce schemas, types, ranges, and permitted values before execution.
- **Restrict available actions.** Limit models to agents and operations permitted for the request.
- **Implement deterministic control flow.** Application code controls dispatch, stopping conditions, and failure handling.
- **Make execution observable.** Record decisions and steps throughout each operation.

## What you will build

Across the hands-on labs you will implement three of the application's reliability boundaries yourself:

- **Typed intent classification** with explicit failure handling, separating an unsupported request from a system that could not run.
- **Bounded orchestration** with an agent allow-list, deterministic dispatch, and stopping conditions the model cannot override.
- **A domain agent** that reaches data through MCP, returns typed results, and fails a step rather than returning false success.

You will also see, but not build, the surrounding boundaries: prompt templating, structured response assembly, and the read-only data path that separates agent queries from the deterministic write path.

## Workshop path

1. Read this page.
2. [Deploy and verify the application](../01-deployment/workshop-deployment.md)
3. Complete the hands-on labs:
   - [Lab 1: Application Overview](../02-hands-on-labs/01-application-overview/lab-1-guide.md)
   - [Lab 2: Intent Classification](../02-hands-on-labs/02-intent-classification/lab-2-guide.md)
   - [Lab 3: Reliable Orchestration](../02-hands-on-labs/03-reliable-orchestration/lab-3-guide.md)
   - [Lab 4: Domain Agent](../02-hands-on-labs/04-domain-agent/lab-4-guide.md)
4. [Clean up workshop resources](../03-cleanup/lab-cleanup.md)

Each implementation lab starts from a known checkpoint with one incomplete behavior. Follow the branch instructions in each lab before making changes.

## Expected outcome

By the end of the workshop you will be able to identify where probabilistic reasoning is valuable, where deterministic control is required, and how to place the boundary between them deliberately rather than by accident.
