# How lab files work

How the workshop ships a complete, runnable application that can still present
Labs 2, 3, and 4 as exercises with code removed.

Status: **design agreed, not yet implemented.**

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

Every lab file becomes three files:

```
orchestrator.py            # shim - decides which of the two below is used
orchestrator_complete.py   # the complete implementation
orchestrator_lab.py        # blanked; the student writes here
```

The shim holds no logic:

```python
"""Selects which Orchestrator the workshop runs. See docs/lab-mechanics."""
import os

if os.getenv("LAB_MODE") == "orchestrator":
    from .orchestrator_lab import Orchestrator
else:
    from .orchestrator_complete import Orchestrator

__all__ = ["Orchestrator"]
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

2. **The shim reads `os.environ` directly**, not the `Settings` class. The shim runs at
   import time, before application configuration is built; going through `Settings` would
   risk an import cycle for no benefit.

3. **Changing `LAB_MODE` requires a restart.** Python caches modules on first import.

4. **The lab guides point at `*_lab.py`.** The guides currently say "open
   `src/app/agents/orchestrator.py`". The anchor comments inside each file are unchanged,
   so only the file path in the prose needs updating.

## Implementation checklist

- [ ] Add `_complete.py` and `_lab.py` for each of the three files; convert the original
      to a shim.
- [ ] Blank the exercise code in each `_lab.py`, leaving the marker comments intact.
- [ ] Add flag parsing to `./start` that exports `LAB_MODE`.
- [ ] Set `LAB_MODE` in `test-lab2`, `test-lab3`, `test-lab4`.
- [ ] Pin `test_orchestrator_errors.py` and `test_react_reasoning.py` to the solution.
- [ ] Update the file paths in the Lab 2, 3, and 4 guides.
- [ ] Verify: a fresh clone runs end to end; each `./start --labN` blanks only its own
      file; each `test-labN` fails before the student writes code and passes after.

## Open questions

- **Repository split.** Whether instructors and students share one repository depends on
  whether anything in `docs/` must stay private.

## Alternatives considered

| Approach                        | Why not                                                                                  |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| A branch per lab                | Switching branches mid-workshop risks losing uncommitted work; four branches to maintain |
| A script that blanks on demand  | Mutates the working tree; the reference is only reachable through git history            |
| Switch at the construction site | Three mechanisms in three places, one of them inside another lab file                    |
