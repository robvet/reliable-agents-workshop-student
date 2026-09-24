# Lab 4: Build a Domain Agent

## Introduction

As you may have noticed, the Reliable Agents accelerator application with which you're working implements a multi-agent architecture. This architecture spreads work across domain-based specialist agents who have deeper expertise in a specific area, such as Assets, Outages, or Crews. The `Orchestrator` is responsible for determining which domain agent runs. Each domain agent answers for its own specialized area and nothing else.

In this lab you will complete `AssetAgent`, the specialist that resolves grid assets and their topology. It receives a strongly-typed `AgentRequest` object carrying the user's prompt and the entities extracted at classification time, turns that request into a domain-language question, reaches operational data through an injected MCP client, and returns a strongly-typed `AgentResult` object, carrying the agent name, its data payload, a trace step for the Execution Trace, and a success flag.

The domain agent is deliberately narrow. It cannot call another domain agent. It cannot open its own database connection. Every capability it has arrives through one injected interface, which is what makes its behavior predictable and its failures easy to locate, all contributing to a more deterministically architected solution.

## Single agent or multi-agent?

A single-agent design puts every tool and every domain rule behind one model call. It is simpler, it makes fewer round trips, and for a small tool surface it is often the right answer.

The cost appears as the surface grows. The more tools and domain rules a single prompt carries, the more room the model has to choose wrong, and there is no natural place to say "this request may use these capabilities and not those."

A multi-agent design splits the work into specialists and puts a deterministic router in front of them.

|                         | Single agent             | Multi-agent                              |
| ----------------------- | ------------------------ | ---------------------------------------- |
| Tool surface per call   | everything               | only the selected domain                 |
| Authorization           | argued inside one prompt | an allow-list enforced outside the model |
| Model calls per request | one                      | one per step                             |
| Testing                 | end to end               | each specialist in isolation             |
| Failure isolation       | hard to attribute        | the trace names the agent                |

Multi-agent becomes the better strategy when domains carry different data, different rules, and different permissions.

### Why this accelerator is multi-agent

This application answers operational questions about assets, events, outages, crews, reliability, and weather. Two properties of that use case make specialists the better fit.

1.) **The domains do not share a data path.** `AssetAgent` reads through the MCP NL-2-SQL service. `WeatherAgent` calls an external forecast API and the map service, and never touches the database. `OutageAgent` reads through MCP but writes through `OutageLifecycleService` and SQLAlchemy. Folding all of that into one agent would gather every dependency in one place and make each one harder to test in isolation.

2.) **Every intent permits a different subset.** `RoutingMap` grants `EVENT_RESPONSE` five agents, `SITUATIONAL_AWARENESS` two, and `UNKNOWN` none at all. Because the agents are separate, that rule is a dictionary lookup that runs before anything executes. Inside a single agent it would have to be argued to a model in a prompt.

The drawback is real. More specialists mean more model calls, more latency, and more moving parts. The control loop you built in Lab 3 is what keeps that bounded, through `MAX_STEPS`, an explicit stop condition, and a duplicate-result check.

## Learning objectives

By the end of this lab you will be able to:

- Implement a domain agent that receives a typed `AgentRequest` and returns a typed `AgentResult`.
- Build a domain-language question from the user's prompt and the typed entities.
- Reach data through an injected interface rather than a concrete client.
- Choose between model-generated SQL and fixed, hand-written SQL, and explain when each is appropriate.
- Fail a step rather than return a result that looks successful.
- Explain why a domain agent cannot call another domain agent.

## Architecture context

![AssetAgent within the application architecture](images/asset-agent-architecture.png)

**Red outline: `AssetAgent`.** The agent you will complete, sitting in the domain agent row with its peers. The `Orchestrator` above selects one of them per step. Notice that no arrow connects one domain agent to another.

**Blue box: the data leg.** Every read agent reaches Postgres this way. `AssetAgent` holds an `IMcpClient` and, through it, calls one of two tools the `mcp_sql` server exposes:

| Tool             | Who writes the SQL             | Model involved |
| ---------------- | ------------------------------ | -------------- |
| `ask(question)`  | `nl2sql.to_sql()` generates it | yes            |
| `run_sql(query)` | the caller supplies it         | no             |

Both land on the same guard. `check()` rejects anything that is not a single `SELECT` or `WITH`, and `_with_limit()` caps the row count. Model-generated SQL gets no privileged path.

That guard is fast-fail convenience, not the security boundary. The real boundary is the pgEdge connection at the bottom of the data leg, which holds a read-only grant, `PGEDGE_DB_ALLOW_WRITES=false`, enforced by the database itself and outside anything the model can influence.

**Green box: the deterministic write path.** The orange line reaches it directly from the REST API, bypassing the orchestrator entirely. It belongs to `OutageAgent`, not to the agent you are building, and is out of scope for this lab. `AssetAgent` has no write path of any kind.

### A pluggable data backend

`mcp_sql` is an MCP **server**. It runs as a separate process and exposes the two tools above over HTTP. The application reaches it through `McpClient`, the client side of that boundary.

Agents never see either one. They depend on `IMcpClient`, an application interface with two methods, and `McpClient` is simply the implementation that ships with the accelerator.

That indirection is what makes the data store pluggable. A different backend, whether or not it speaks MCP, needs only its own `IMcpClient` implementation, with no change to any agent. It is also what lets this lab's tests hand the agent a mock and run offline.

### Orchestration sequence

The following sequence traces one call to `AssetAgent.handle()`, from the orchestrator's dispatch to the typed result it returns.

```mermaid
sequenceDiagram
    participant Orchestrator
    participant Agent as AssetAgent
    participant Client as IMcpClient
    participant Server as mcp_sql server
    participant DB as Postgres

    Orchestrator->>Agent: handle(AgentRequest)
    Agent->>Agent: Build domain-language question
    Agent->>Client: query(question)
    Client->>Server: ask(question)
    Server->>Server: nl2sql.to_sql() - model call
    Server->>Server: check() and apply row limit
    Server->>DB: Execute generated SQL
    DB-->>Server: Rows
    Server-->>Client: sql, rows, reasoning
    Client-->>Agent: Payload
    Agent->>Agent: Normalize into assets and count

    alt Downstream traversal requested
        Agent->>Agent: Build fixed traversal SQL
        Agent->>Client: run_sql(fixed SQL)
        Client->>Server: run_sql(query)
        Server->>Server: check() and apply row limit
        Server->>DB: Execute caller SQL
        DB-->>Server: Rows
        Server-->>Client: Rows
        Client-->>Agent: Downstream assets
    end

    Agent-->>Orchestrator: AgentResult
```

Four things are worth noticing.

**The model appears once, inside the server.** `nl2sql.to_sql()` is the only probabilistic step in the sequence. Everything before it assembles a question, and everything after it is validation, execution, and normalization.

**Both SQL sources pass the same guard.** Whether the SQL came from the model or from the agent's own hand-written traversal query, `check()` and the row limit run before the database sees it.

**The optional branch is not a new model decision.** It runs only when the intent classifier already set `needs_downstream_assets`, decided once before the ReAct loop began. The traversal SQL is hand-written, so the same asset returns the same rows every time.

**The agent's only outbound arrow is to `IMcpClient`.** There is no line from `AssetAgent` to another domain agent, because there is nothing in the class to draw one with.

#### What `needs_downstream_assets` means

Grid assets form a hierarchy: substation, then feeder, then transformer, then service location, then meter. A question like "what is affected by the outage at FDR-204?" asks for everything below that asset in the hierarchy, not for the asset itself.

`needs_downstream_assets` is a boolean the intent classifier sets when it recognizes that framing. It is one model judgment made once per turn, not a decision re-made on every ReAct step.

The traversal it triggers uses hand-written SQL rather than a generated query, and the reason is worth reading carefully. When this traversal was left to NL-2-SQL, the model performed the joins on some calls and skipped them on others, so identical questions returned different answers from one run to the next. The fix was not a better prompt. It was moving the traversal out of the model's hands entirely.

That is this workshop's thesis in a single feature: one model judgment, then fixed code.

## Lab exercise

You will complete `AssetAgent`'s model-generated read path, from prompt construction through typed result creation.

### What is already provided

- `AgentRequest`, `AgentResult`, `Entities`, and `TraceStep`.
- `BaseDomainAgent`, including the typed `handle()` contract.
- `IMcpClient`, with `query()` for domain-language questions and `run_sql()` for fixed read-only SQL.
- Dependency injection of `IMcpClient` through the `AssetAgent` constructor.
- The fixed downstream traversal branch and its hand-written SQL.
- Logging, the result helper, and orchestration-level error handling.

Open `src/app/agents/asset_agent.py`. Each step below begins with a comment that is already in the file. Find that comment and add the code directly beneath it. Work through `handle()` first, then the two helper methods it calls.

#### Step 1: Ask the MCP client for asset data

The first block in `handle()` builds the domain-language question, records it, and sends it across the MCP boundary.

```python
# Build a domain-language question from the typed request. AssetAgent
# describes the data it needs; the MCP service decides how to query it.
prompt = self._build_prompt(request)

# Record the exact question crossing the MCP boundary for observability.
logging.info("AssetAgent: reasoning (question)=%s", prompt)

# Ask the injected MCP client to resolve the domain question. The client
# calls the NL-2-SQL service and returns its structured payload.
try:
    payload = await self._mcp.query(prompt)
except Exception:
    # Do not turn a tool failure into a successful empty result. Record
    # the fault and re-raise it so the orchestrator stops this request.
    logging.exception("AssetAgent: MCP query failed; failing the step")
    raise
```

The agent does not construct `McpClient` and does not open a database connection. It knows only the `IMcpClient` contract supplied to its constructor.

> **Deterministic engineering: one probabilistic hop, explicitly bounded.**
> The model call lives inside the MCP service, not inside this agent. `AssetAgent` builds a question with ordinary code, hands it across a typed boundary, and everything it does after that is validation and normalization. When a request misbehaves, you know whether the fault was in the question the code assembled or the SQL the model generated, because those are separate steps in separate processes.

The `raise` is equally important. An MCP failure is not an empty successful result. Re-raising lets the orchestrator emit an error event and stop, instead of composing an answer from missing evidence.

> **Deterministic engineering: fail loudly, never silently.**
> `raise` costs one word and buys the whole failure contract. A caught-and-swallowed exception would return `assets: [], count: 0` - indistinguishable from "no assets matched." Downstream code would compose a confident, wrong answer. Propagating the exception makes "we could not reach the data" a distinct outcome from "the data says none."

#### Step 2: Normalize the payload and keep the evidence

Still in `handle()`, convert the successful payload into the agent's data shape and attach the evidence the tool returned.

```python
# Normalize the successful MCP payload into the stable asset data shape
# expected by the rest of the typed pipeline.
data = self._parse(payload)

# Preserve the question, generated SQL, and server reasoning as evidence.
# These fields travel with the result and make the data leg inspectable.
sql = payload.get("sql") if isinstance(payload, dict) else None
reasoning = payload.get("reasoning") if isinstance(payload, dict) else None
data["sql"] = sql
data["question"] = prompt
data["reasoning"] = reasoning
logging.info("AssetAgent: rows=%d sql=%s", data["count"], sql)
```

These values make the data leg inspectable without asking the model to explain itself again. The generated SQL is evidence returned by the tool; the domain agent does not execute or rewrite it.

> **Deterministic engineering: normalize at the boundary.**
> Every backend shape is resolved here, once, at the edge. The rest of the pipeline reads `data["assets"]` and `data["count"]` and never asks which shape arrived. Swapping the backend changes this one method; nothing downstream notices.

> **Deterministic engineering: carry the evidence, not just the answer.**
> The question, the SQL, and the server's reasoning travel with the result. When an answer is disputed, you replay exactly what was asked and exactly what ran - no re-prompting the model to explain itself, which would only produce a fresh guess about its own past behavior.

The downstream traversal block that follows is already provided. Leave it in place. It is a separate deterministic operation triggered by the typed `needs_downstream_assets` flag, and it is the subject of Tests 5 and 6.

#### Step 3: Return a typed result

Finish `handle()` with the provided `_result()` helper.

```python
# Return a validated AgentResult rather than prose. The trace step carries
# a concise summary and the evidence operators need to inspect this hop.
return self._result(
    data=data,
    ok=True,
    summary=f"resolved assets ({self._describe(request)}); {data['count']} found",
    detail={
        "question": prompt,
        "tool": "ask",
        "sql": sql or "",
        "reasoning": reasoning or "",
        "rows": str(data["count"]),
    },
)
```

`_result()` constructs the `AgentResult` and its `TraceStep`. The return value is validated at the agent boundary, so the orchestrator receives structured evidence rather than a prose answer.

> **Deterministic engineering: validate at every hop.**
> `AgentResult` is a Pydantic model, so a malformed result fails here, at the agent that produced it, rather than surfacing as a confusing error in the assembler three steps later. Typed contracts turn "the output was wrong" into "this agent violated its contract."

#### Step 4: Build the domain-language question

Move to `_build_prompt()`, the helper Step 1 called. It turns the typed entity slots into domain terms and assembles the question.

```python
# Translate each populated entity into a domain label. These values scope
# the question without asking AssetAgent to generate SQL.
if e.asset_id:
    filters.append(f"asset {e.asset_id}")
if e.feeder:
    filters.append(f"feeder {e.feeder}")
if e.substation:
    filters.append(f"substation {e.substation}")
if e.location:
    filters.append(f"location {e.location}")

# Preserve the user's complete wording so constraints that are not entity
# slots, such as time ranges, counts, and exclusions, are not discarded.
question = f"Answer the asset portion of this request: {request.user_prompt}"

# Add the typed starting scope when present. The traversal guidance keeps
# an affected-assets request from becoming an incorrect exact-match query.
if filters:
    question += (
        f" Scope the query starting from: {', '.join(filters)}. If the request asks "
        "about assets affected, impacted, or downstream of that starting point (e.g. "
        "due to an outage), that starting asset is the ROOT of the traversal, not an "
        "exact-match filter - include it and everything downstream of it. Only treat "
        "it as an exact-match filter (return just that one asset) when the request is "
        "asking about the asset itself with no affected/impacted/downstream framing."
    )
```

These are domain labels, not table or column names. The agent states what it needs; the NL-2-SQL service owns how that request maps to the database.

> **Deterministic engineering: the model gets a narrower job.**
> Entity extraction already happened, once, at classification. The agent reads typed slots instead of re-parsing the sentence, so `TX-17` cannot become `TX-71` on a retry. Each model judgment is made one time and then carried forward as data.

The original user wording matters. Reducing the prompt to a generic request such as "return assets" would discard constraints such as time windows, counts, inspection state, or exclusions that were never promoted into entity slots.

> **Deterministic engineering: preserve the input you did not model.**
> Entity slots capture what you anticipated. The user's raw wording carries what you did not - time windows, exclusions, aggregations. Passing both means an unmodeled constraint degrades into a weaker query, not a silently wrong one.

The fixed-schema reference below this block is already provided, along with `return question`. Leave both in place. That reference describes allowed domain values; it does not inspect live rows or choose a query plan.

#### Step 5: Accept the supported payload shapes

Finally, complete `_parse()`, the helper Step 2 called.

```python
# Accept the supported successful response shapes: rows returned directly
# as a list, or rows nested under a known dictionary key.
if isinstance(payload, list):
    assets = payload
elif isinstance(payload, dict):
    assets = payload.get("rows") or payload.get("assets") or []
else:
    assets = []

return {"assets": assets, "count": len(assets)}
```

This is normalization, not error recovery. Transport and tool failures were already raised in Step 1. `_parse()` handles only the successful payload shapes the agent supports.

> **Deterministic engineering: handle the shapes you support, reject the rest.**
> The `else: assets = []` branch is not a catch-all. Failures already raised in Step 1. This method maps _known successful_ shapes and treats anything else as empty rather than guessing at an unfamiliar structure.

### Coding wrap-up

You have completed the domain-agent read path. The agent turns typed context into a domain question, calls one injected capability, normalizes successful output, preserves tool evidence, and returns a validated result. It does not select another agent, create a data connection, or render the final user response.

Notice the shape of what you built: one model call, bounded by a typed request going in and a validated result coming out, with deterministic code on both sides. Add a second agent and the property holds - which is what makes a multi-agent system debuggable instead of merely impressive.

> **Note:**
>
> 1. Save your changes.
> 2. Move to the **Test activities** section.

## Test activities

Let's test `AssetAgent` in isolation and confirm that it preserves the user's request, returns typed evidence, propagates failures, and runs deterministic traversal only when the classified request requires it.

A set of predefined tests can be found in `tests/test_asset_agent.py`, in the class `TestAssetAgent`. They cover six responsibilities of a reliable domain agent:

1. Preserve the complete user request and MCP evidence.
2. Add typed asset scope to the domain-language question.
3. Return a validated `AgentResult` and `TraceStep`.
4. Propagate an MCP failure instead of returning false success.
5. Execute fixed downstream traversal when the classifier requests it.
6. Skip downstream traversal when the classifier does not request it.

`IMcpClient` is replaced with controlled mocks, so no MCP server, model, or database is required. The tests run offline and produce the same result every time.

The repository includes a `test-lab4` script so you can skip the longer pytest command. Run all six tests from the repository root:

```bash
./test-lab4
```

Expect `6 passed`.

#### Test 1: The user request and MCP evidence are preserved

**How it works:** The mocked MCP client returns one aggregate row together with generated SQL and reasoning. The test confirms that the agent sends the user's complete request to MCP and preserves the returned rows, SQL, question, and reasoning in `AgentResult.data`.

```bash
./test-lab4 -k preserves_user_request
```

**Expected result:** The complete user request appears in the MCP question, all returned evidence appears in `AgentResult.data`, and the test reports `PASSED`.

#### Test 2: Typed entity scope is added to the question

**How it works:** The test constructs an `AgentRequest` containing asset, feeder, substation, and location entities, then calls `_build_prompt()` directly. This isolates deterministic prompt construction without invoking MCP.

```bash
./test-lab4 -k appends_typed_asset_filters
```

**Expected result:** The generated question preserves the user's request and adds the asset, feeder, substation, and location extracted during intent classification. The test reports `PASSED`.

#### Test 3: The agent returns a typed result and trace

**How it works:** The mocked MCP client returns one asset row. The test confirms that `handle()` normalizes the row and returns a successful `AgentResult` containing a `resolve_asset` trace step.

```bash
./test-lab4 -k returns_typed_result
```

**Expected result:** The result identifies the `asset` agent, reports one normalized row, and includes a successful `resolve_asset` trace step. The test reports `PASSED`.

#### Test 4: MCP failure propagates

**How it works:** The mocked MCP client's `query()` method raises `RuntimeError`. The test confirms that `AssetAgent` re-raises the exception rather than converting the failure into an empty successful result.

```bash
./test-lab4 -k propagates_mcp_failure
```

**Expected result:** The `MCP unavailable` exception escapes `AssetAgent.handle()`, and the test reports `PASSED`.

#### Test 5: Classified downstream scope uses fixed SQL

**How it works:** The request contains an asset identifier and sets `needs_downstream_assets=True`. The normal MCP query returns the initial asset result, and the mocked `run_sql()` call returns the downstream rows. The test verifies that the fixed traversal query checks the named asset at the substation, feeder, and transformer levels.

```bash
./test-lab4 -k runs_fixed_downstream_query
```

**Expected result:** The agent calls `run_sql()` with the fixed traversal query and adds the returned rows to `AgentResult.data["downstream_assets"]`. The test reports `PASSED`.

#### Test 6: Downstream traversal requires the classifier flag

**How it works:** The request contains an asset identifier but leaves `needs_downstream_assets=False`. The test confirms that an asset identifier alone does not authorize the additional traversal.

```bash
./test-lab4 -k skips_downstream_query
```

**Expected result:** The agent does not call `run_sql()` and does not add `downstream_assets` to the result. The test reports `PASSED`.

Together, these last two tests capture the deterministic boundary: the classifier makes the traversal judgment once, and fixed code either executes or skips the traversal from that typed decision.

With all six tests passing, start the application and submit an asset question such as:

```text
How many transformers were inspected in the last 30 days, excluding retired assets?
```

In the Execution Trace, confirm that the orchestrator dispatches `asset`, the agent records the MCP question and generated SQL, and the final response uses the returned evidence.
