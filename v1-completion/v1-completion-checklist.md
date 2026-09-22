# Deployment Game Plan

Branches: 09-12 Adding Actions  
 09-21-v1-completion-tasks

## Completed Tasks:

- Business case.
- Arch Diagram

- Review Fallback Paths
- Add model icon for those components with model calls

## Outstanding Tasks:

- Arch diagram
- Review Fallback Paths
- Add model icon for those components with model calls

- Suffix all model files with model
- Suffing all data classes with data

## Labs

- App Overview Lab
  - make it interactive
  - Review main/routing

- Intent Classification Lab
  - What it is/what it does
  - Why it's critical to reliable agents
  - Study the system prompt

- Orch Lab
- Agentic Workflow

- Agent Lab (Outage agent)

- Update Business Case

- Update Home Page

- Lab Doc
  - System Overview
  - Deterministic Engineering Overview

  - What you'll create:
    - Intent Classification
    - ReACT Loop
    - An Agent

- For docs, make docs follow skill format where user could query something in the system? Example: How does xyz work? Or, what is schema of the abc table? Or, tell me what the asset agents does?

- Cleanse project
- Cleanse docs
- Add message box and spinner while Outages are loading. But, make messagebox and spinner generic for any loading situation

- Update Data Model
  - Add in the DDL as-is (no schema migration, no live-DB risk, fully reversible), and just stop the app from generating/reading them. One caveat I put in the doc: an empty, unused table can read as "wait, what's this for?" to someone looking at the schema cold later — worth a one-line DDL comment marking them dormant/reserved if you go this route, so it doesn't become a mystery down the line.

2:27 PM
1m 4s
•

- Update Business Case

Inside data fodler, separate subfolder for models and another for (db) plumbing -- call it repository??

Update Architecture, Data Diagram, and Business Case

Have Sonnet 5 to create an ontology

Once you create an outage or change the status, refresh the list of outages - also add refresh button to Outages

- Could we subsitutue a json representation to mimic the database, if we needed

What is matching Rule 7:
Intent: DOMAIN_LOOKUP (96%)
Reasoning pattern: ReACT Reasoning Pattern
New Conversation
The message asks “what is the status of XFMR-1042,” which is a read-only query about a specific asset, matching rule 7.

Updating Docs

What it is
What it does
How it works
How to invoke it

Testing:

- Identify the applicable Failure Modes and writes tests for each

Create Docs as Skills:
On your question — worth separating two different things that both get called "skills" here:

This app already has a real runtime "skills" system (src/app/skills/\*.md, e.g. event_severity_classification.md, outage_note_triage.md): a document an LLM reads at the moment it has to make a judgment call (e.g. "is this severity HIGH?"), paired with an enforced threshold the code double-checks. That pattern only makes sense when an AI is actually deciding something.
This asset-status doc is the opposite case — the whole point of today's fix was removing the AI from that decision and making it a fixed table lookup in code. There's no judgment left for an LLM to make here, so turning it into a "skill" would be re-introducing the exact non-determinism we just spent hours removing.
Where a docs-as-skill idea would make sense later: a separate "explain how this works" FAQ tool the chat agent can consult when someone asks a conceptual question like "why does status work this way" — that's a documentation-retrieval feature, not a decision-rubric skill, and would be a new, different piece of plumbing. Worth a real discussion after your deadline, not something to fold into the existing skills system as-is.

---

## Completed Tasks:

---

Friday - 09/18

Sat - 09/19

Sun - 09-20

Mon - 09-21

Tue - 09/22

Wed - 09/23
