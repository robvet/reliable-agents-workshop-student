# Orchestration Lab Notes

- Lab 3: Customer gets a shell of the Orchestrator class and build out the workflow and implementation details

- Lab 3 (Orchestrator) — this one worries me. It's not sized like the other two.
  The real orchestrator.py isn't just "dispatch a loop" — it's:

The ReAct loop + MAX_STEPS cap
Allow-list enforcement against RoutingMap
A no-progress dedup guard (comparing AgentResult.data minus volatile keys)
Contradiction-retry handling that lives in ReActReasoning, not here, but the orchestrator has to interpret it
Streaming StreamEvents at every step
Three separate try/except blocks with the "HTTP 200 already sent, no error path throws a 500" constraint
Conversation memory load/append

- Scope it down: pre-provide the streaming/error/memory scaffolding, and have the customer fill in only the core loop body (propose → validate allow-list → dispatch → observe → stop-condition). That's the teachable "reliability" core anyway — the rest is plumbing they don't need to re-derive.
  Keep it full-size but budget it as 2x a normal lab.
  Either way, I'd explicitly decide before writing it.
