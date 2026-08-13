# SealedKeep

**Only real improvements survive.**

SealedKeep is infrastructure for agentic research loops. An agent proposes a change, a fixed evaluation command runs, and the change is **kept only if the declared metric actually improved**. Everything else is reverted. Every trial is a Git commit. Failed branches stay as evidence.

Control, evaluation, and budgets live **outside** the model. The loop can run overnight, be audited later, and be handed to another agent or a human without trusting a chat transcript.

| Contract | Status |
| --- | --- |
| API / schemas | `v0.1.2` (additive; `v0.1.0-frozen` still accepted) |
| OpenAPI | `0.1.2` |
| Phase | 6 — production pilot (sealed keep-gate, frontier, leaves) |
| Language | Python 3.11+ |

## Why it exists

One-shot prompts do not survive long-horizon work. Without external verifiability, agentic systems typically:

- **Hallucinate progress** — claim a better metric without a real run
- **Lose lineage** — no path from “best result” back to hypothesis, parent commit, and evaluator decision
- **Overwrite the eval surface** — edit the test or the metric definition
- **Blow budgets** — unbounded tokens, tool calls, or graph writes
- **Mix work history with knowledge** — one undifferentiated store for both

SealedKeep treats those as design constraints, not operational surprises.

> A keep that cannot be lied to is worth more than a knowledge graph that can be written by anything.

## How a loop works

```
inspect → propose → commit → evaluate → keep | revert → log
```

1. **Measured experiment.** The agent edits only the allowed surface. A fixed `run_command` produces stdout. The metric is parsed from that stdout. `metric_override` is always rejected.
2. **Sealed keep.** A keep is a certificate, not a lucky seed. Optional `keep_gate.mode: paired_pace` requires more than one seed before a keep is sealed.
3. **Lineage.** Every trial is a Git commit in a DAG. Leaves are the frontier. Reverted trials remain addressable.
4. **External control.** Objective, protected files, metric, comparison function, budgets, and keep/revert rules live in a versioned control document — not in the prompt.
5. **Optional knowledge graph.** Claims, sources, and provenance sit on top of the DAG. Graph writes are **off** on the agent path unless you pass `--enable-graph-writes`.

Central traceability invariant:

```
objective → plan → artifact → source → graph path → evaluator decision → bounded execution record
```

The included demo (`examples/demo_workspace/`) is a tiny CPU trainer: mutate hyperparameters in `train.py`, never touch `prepare.py`, minimize `val_loss`, keep only on real improvement.

## Non-negotiable rules

| Rule | Enforcement |
| --- | --- |
| **Hostile metrics** | `kept` only from a real `run_command` stdout parse. Last regex match wins (anti fake-print). `metric_override` always `rejected`. |
| **Git is truth** | DAG parents and objects come from bare Git. No orphan `register_node` in normal mode. |
| **Protected eval surface** | Agents cannot edit protected paths (e.g. `prepare.py`) or the holdout. |
| **Working tree stays runnable** | Crash or reject → automatic revert to `best_commit`. |
| **Bounded context** | `ah context` / `POST /dag/context` packs a budgeted subgraph. Token estimate is **chars/4**, not a tokenizer — do not bill from it. |
| **KG humility** | Graph writes default **off**. |
| **Athlete first** | `ah agent-run --loop <id>` is a heuristic agent. No LLM required to prove the loop. |

See `agentic_platform.invariants` and [MASTER-PLAN.md](MASTER-PLAN.md) §7 for the full list.

## Architecture

Four layers. They do not collapse into one store.

| Layer | Concern | Package |
| --- | --- | --- |
| 1 Measured loop | Verifiable iteration + reversibility | `agentic_platform.loops` |
| 2 Commit DAG | Experiment lineage + message board | `agentic_platform.dag` |
| 3 Software 3.0 | Control docs, evaluators, budgets | `control`, `eval`, `runs` |
| 4 Knowledge graph | Durable claims + provenance | `agentic_platform.graph` |

HTTP surfaces (frozen contracts under `contracts/`):

| API | Base path |
| --- | --- |
| Control document | `/control` |
| Loop execution | `/loops` |
| DAG / board | `/dag` |
| Knowledge graph | `/graph` |
| Evaluation | `/eval` |
| Budget and audit | `/runs` |

## Install

Requires Python 3.11+.

**Unix / macOS**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q
```

Entry points: `ah` (CLI) and `agentic-api` (HTTP).

## Quick start

Point the platform at a data directory, then start the API or use the CLI.

```bash
export AGENTIC_DATA=./data
agentic-api
```

```powershell
$env:AGENTIC_DATA = ".\data"
agentic-api
```

```bash
ah leaves
ah context --budget-tokens 2000
ah agent-run --loop <loop_id> --max-trials 8
```

Local dev key (do not use in a shared environment): `X-Agent-Key: architect-dev-key`.

Health: `GET /health` · Ready: `GET /ready`.

## Demo (no LLM, ~15 minutes)

Bootstrap a control document and loop, run the heuristic athlete, inspect the frontier, then prove a fake metric cannot keep.

```bash
export AGENTIC_DATA=./data
ah demo bootstrap
ah demo athlete --loop <loop_id> --max-trials 8
ah leaves
ah board
ah context --budget-tokens 2000
ah demo hostile --loop <loop_id>
ah demo show --loop <loop_id>
```

Expected: athlete produces `kept` / `reverted` trials; hostile step returns `passed: true`, `best_unchanged: true`, and an `INV-02` reject.

Full room script: [docs/demo.md](docs/demo.md). Trainer: `examples/demo_workspace/`.

## Operations

Production should set auth and rotate the admin token. See [docs/runbook.md](docs/runbook.md).

```bash
export AGENTIC_REQUIRE_AUTH=1
export AGENTIC_ADMIN_TOKEN='<long-random>'
export AGENTIC_REJECT_UNKNOWN_KEYS=1
agentic-api
```

| Control | Behavior |
| --- | --- |
| Sandbox | Child env scrubbed of `*KEY*`, `*SECRET*`, `*TOKEN*`; `run_command` allowlisted to `python script.py` |
| Secret scan | Diffs rejected on AWS keys, GitHub PATs, private-key blocks |
| Auth | `X-Agent-Key`; `POST /auth/keys` to issue; `GET /auth/agents` lists fingerprints |
| Recovery | `POST /loops/{id}/recover` resets to `best_commit` and re-runs the metric |
| CI | `.github/workflows/ci.yml` · release bar is `pytest -m release_gate` plus `GET /ready` |

## Documentation

| Document | What it is |
| --- | --- |
| [MASTER-PLAN.md](MASTER-PLAN.md) | Authority: vision, layers, invariants, acceptance tests, roadmap |
| [docs/demo.md](docs/demo.md) | Live demo script |
| [docs/runbook.md](docs/runbook.md) | Start/stop, auth, recovery, sandbox |
| [docs/release-gates.md](docs/release-gates.md) | Named pytest gates that must stay green |
| [docs/phase6-technical-plan.md](docs/phase6-technical-plan.md) | Phase 6 work packages |
| [docs/bibliography.md](docs/bibliography.md) | Sources and Phase 6 candidates |
| `docs/adr/` | Architecture decision records |
| `contracts/` | Frozen OpenAPI + JSON schemas |

ADRs: [001 storage](docs/adr/ADR-001-storage-and-runtime.md) · [002 phase scope](docs/adr/ADR-002-phase-scope-sections-1-8.md) · [003 Git-authoritative DAG](docs/adr/ADR-003-git-authoritative-dag.md) · [004 honesty exit](docs/adr/ADR-004-kaparthy-correction-exit.md) · [005 hardening](docs/adr/ADR-005-phase5-hardening.md) · [006 Phase 6](docs/adr/ADR-006-phase6-top-slice.md)

## What this is not

- Not a training framework and not a weight-update loop.
- Not an LLM product. The athlete is a hyperparameter grid; plug in your own solver if you want a model.
- Not a guarantee that `val_loss` drops. The ledger is the product, not a magic score.
- Not a knowledge-graph-first system. Graph writes stay off until you opt in.

Influences (Karpathy autoresearch / AgentHub, Software 3.0 control, Anthropic workflow notes) are collected in [docs/bibliography.md](docs/bibliography.md). They do not override the master plan.
