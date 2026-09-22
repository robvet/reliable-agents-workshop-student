# Reliable Agents Workshop

This workshop guides you through deploying, exploring, and completing a reliable multi-agent application for asset-event response.

## Learning outcomes

By the end of the workshop, you will be able to:

- Explain where probabilistic model behavior ends and deterministic control begins.
- Implement structured intent classification with explicit failure handling.
- Build a bounded orchestration loop with deterministic validation and routing.
- Implement a domain agent that accesses data through MCP.
- Recognize the security boundary between read-only agent access and deterministic writes.

## Workshop path

1. [Set up your environment](00-environment-setup/README.md)
2. [Deploy and verify the application](01-deployment/README.md)
3. Complete the hands-on labs:
   - [Lab 1: Application Overview](02-hands-on-labs/01-application-overview/README.md)
   - [Lab 2: Intent Classification](02-hands-on-labs/02-intent-classification/README.md)
   - [Lab 3: Reliable Orchestration](02-hands-on-labs/03-reliable-orchestration/README.md)
   - [Lab 4: Domain Agent](02-hands-on-labs/04-domain-agent/README.md)
4. [Clean up workshop resources](03-cleanup/README.md)

## Repository checkpoints

Each implementation lab starts from a known checkpoint with one incomplete behavior. Follow the branch instructions in each lab before making changes.
