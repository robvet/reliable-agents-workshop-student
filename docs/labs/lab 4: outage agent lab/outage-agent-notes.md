# Outage Agent Notes

- Lab 4: Customer gets a shell of the outage_agent class and builds out the implementation detail

- Lab 4 (OutageAgent) — recommend narrowing scope.
  The full class mixes two different lessons: (a) the NL2SQL read path via handle()/\_build_prompt/\_parse — the reusable "how a domain agent talks to MCP" pattern, and (b) deterministic writes + note-triage skill escalation (hazard-keyword double-check against the model's opinion) in transition(). (b) introduces the whole SkillRepository/skills concept, which nothing in Labs 1–3 sets up. I'd make the lab's build-target just handle() + helpers, and treat the write/note-triage path as a guided walkthrough (read-only, discussed but not built) — or its own optional Lab 5 if skills are worth a dedicated lesson later.
