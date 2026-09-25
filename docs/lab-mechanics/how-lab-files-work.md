# How lab files work

How the workshop ships a complete, runnable application that can still present
Labs 2, 3, and 4 as exercises with code removed.

Status: **implemented.**

## The problem

Three files hold the code students write:

| Lab | File                                      | Lines |
| --- | ----------------------------------------- | ----- |
| 2   | `src/app/intent/llm_intent_classifier.py` | 136   |
| 3   | `src/app/agents/orchestrator.py`          | 251   |
| 4   | `src/app/agents/asset_agent.py`           | 194   |

Lab 1 is an instructor-led tour of the **running** application. It tells students to
start the app, submit prompts, and read the Execution Trace. So the repository cannot
ship with those three files blanked - Lab 1 would be broken before anyone writes a line.

But each lab needs its file blank when the student reaches it.

## The approach: one repository, a toggle at the import

Each lab file keeps its name and its complete implementation, and gains one sibling:

```
orchestrator.py       # the complete implementation, plus a toggle at the bottom
orchestrator_lab.py   # blanked; the student writes here
```

The toggle is appended to the end of the existing file. Everything above it is
unchanged:

```python
class Orchestrator:
    ...the complete implementation...


# Lab 3 toggle. Python binds names in order, so the last binding is what
# importers receive. LAB_MODE may name one component or several, comma
# separated, so ./start --all-labs can swap all three at once.
import os as _os

if "orchestrator" in _os.getenv("LAB_MODE", "").split(","):
    from .orchestrator_lab import Orchestrator  # noqa: F811
```

### Why this works

In Python, `from X import Y` means "run module X, then give me whatever `Y` names
inside it." The caller never learns where `Y` was defined. A module that imports a name
rather than defining one is therefore indistinguishable to everyone downstream.

That means **every existing import stays exactly as written**. All nine of them:

| File                                       | Line | Import                                             |
| ------------------------------------------ | ---- | -------------------------------------------------- |
| `src/app/main.py`                          | 25   | `from .agents.orchestrator import Orchestrator`    |
| `src/app/api/routes.py`                    | 15   | `from ..agents.orchestrator import Orchestrator`   |
| `src/app/agents/orchestrator.py`           | 14   | `from ..intent.llm_intent_classifier import ...`   |
| `src/app/agents/domain_agent_factory.py`   | 2    | `from .asset_agent import AssetAgent`              |
| `tests/test_lab2_llm_intent_classifier.py` | 5    | `from app.intent.llm_intent_classifier import ...` |
| `tests/test_lab3_reliable_orchestration.py`| 6    | `from app.agents.orchestrator import Orchestrator` |
| `tests/test_asset_agent.py`                | 5    | `from app.agents.asset_agent import AssetAgent`    |
| `tests/test_orchestrator_errors.py`        | 1    | `from app.agents.orchestrator import Orchestrator` |
| `tests/test_react_reasoning.py`            | 6    | `from app.agents.orchestrator import Orchestrator` |

No composition root changes. `main.py`, `routes.py`, and `domain_agent_factory.py` are
untouched.

### Why the toggle is not at the construction site

The obvious alternative - a config switch where each class is built - does not work
cleanly here. The three construction sites are in three different places, and one of
them is inside another lab file:

| Class                 | Constructed in               |
| --------------------- | ---------------------------- |
| `Orchestrator`        | `main.py:163`                |
| `LlmIntentClassifier` | **`orchestrator.py:53`**     |
| `AssetAgent`          | `domain_agent_factory.py:71` |

Lab 2's switch would live inside Lab 3's file, so `orchestrator_lab.py` would need its
own copy of it. Intercepting the import avoids the problem entirely.

## Running a lab

`LAB_MODE` names the one component in lab mode. Unset means everything runs the
solution.

```bash
./start              # all solution - Lab 1 tour works on a fresh clone
./start --lab2       # LAB_MODE=intent
./start --lab3       # LAB_MODE=orchestrator
./start --lab4       # LAB_MODE=asset
./start --all-labs   # optional finale: all three are the student's code
```

**One lab is in lab mode at a time.** A completed lab runs its solution during the next
lab. That is deliberate:

- If the student's Lab 2 passes its tests, it is equivalent to the solution by
  definition - that is what the tests assert.
- It keeps the blast radius of a failure to one file. A student debugging Lab 3 is not
  also debugging a subtle flaw their Lab 2 tests did not catch.

`--all-labs` preserves the end-to-end payoff for anyone who wants it, without making it
load-bearing.

## Grading

Each test script must force its own component into lab mode. Without this, the tests
import the solution and pass on a fresh clone, verifying nothing:

> **Note:** Lab 3's tests always run against `orchestrator_lab.py`. Without pinning
> `LAB_MODE`, the tests would import the complete implementation and pass before the
> student has written anything.

```bash
# test-lab3
LAB_MODE=orchestrator PYTHONPATH="$REPO_ROOT/src" exec ... pytest tests/test_lab3_reliable_orchestration.py
```

### The other orchestrator tests

`tests/test_orchestrator_errors.py` and `tests/test_react_reasoning.py` also import
`Orchestrator`. Verified: all 9 pass under `LAB_MODE=orchestrator`, because neither
exercises the blanked control loop. No pinning is required today, but a future test that
drives the loop would need it.

## Rules

1. **A blanked file must be valid Python.** `orchestrator.py` imports the other two lab
   modules at import time, so a syntax error in any one breaks the others. Blank a method
   body with a placeholder, never with deleted code:

   ```python
   async def classify(self, user_prompt: str, history: list[dict] | None = None) -> IntentResult:
       """..."""
       raise NotImplementedError("Lab 2: implement the classification workflow")
   ```

2. **The toggle reads `os.environ` directly**, not the `Settings` class. It runs at
   import time, before application configuration is built; going through `Settings` would
   risk an import cycle for no benefit.

3. **Changing `LAB_MODE` requires a restart.** Python caches modules on first import.

4. **The lab guides point at `*_lab.py`.** The guides currently say "open
   `src/app/agents/orchestrator.py`". The anchor comments inside each file are unchanged,
   so only the file path in the prose needs updating.

## Implementation checklist

- [x] Append the toggle to each of the three lab files.
- [x] Add `*_lab.py` for each, with the exercise code blanked and the marker comments
      intact.
- [x] Add flag parsing to `./start` that exports `LAB_MODE`.
- [x] Pin `LAB_MODE` in `test-lab2`, `test-lab3`, and `test-lab4`.
- [x] Confirm `test_orchestrator_errors.py` and `test_react_reasoning.py` still pass
      under `LAB_MODE` - they do; neither reaches the blanked code.
- [x] Point the Lab 2, 3, and 4 guides at `*_lab.py` and name the `./start --labN` flag.
- [x] Verify: default mode runs 38 tests green; each toggle swaps only its own component;
      each `test-labN` fails on the blank file and passes once the code is filled in.

## Adding a fourth lab

1. Append the toggle block to the file, choosing a `LAB_MODE` name.
2. Copy the file to `*_lab.py` and blank the exercise code, keeping every marker comment.
3. Add the flag to `./start` and pin `LAB_MODE` in the new `test-labN`.
4. Point the guide at `*_lab.py`.

## Open questions

- **Repository split.** Whether instructors and students share one repository depends on
  whether anything in `docs/` must stay private.

## Alternatives considered

| Approach                        | Why not                                                                                  |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| A branch per lab                | Switching branches mid-workshop risks losing uncommitted work; four branches to maintain |
| A script that blanks on demand  | Mutates the working tree; the reference is only reachable through git history            |
| Switch at the construction site | Three mechanisms in three places, one of them inside another lab file                    |
