# Agentic Research Platform (kaparthy)

Production oriented implementation of the **Agentic Research Platform** Master Plan: measured loops, commit DAGs (AgentHub), Software 3.0 control/evaluation/budgets, and a knowledge-graph overlay.
This repo was influenced by a number of papers that read about or from Kaparthy.

**Contract version:** `v0.1.2` (additive; `v0.1.0-frozen` still accepted) · OpenAPI `0.1.2`  
**Authority:** IT Architect  
**Phase:** 6 in progress (WP6 gates + sealed keep + frontier + leaves)

## What this application does

This platform is infrastructure for **agentic research loops**—systems where AI agents (or simple heuristic agents) iteratively improve a measurable objective under hard constraints.

In practice it:

1. **Runs measured experiments** — An agent proposes a change, runs a fixed evaluation command, and keeps the change only if the declared metric actually improved. Reverts are automatic; the working tree stays runnable.
2. **Records experiment lineage** — Every trial is a Git commit in a DAG (AgentHub-style). Leaves are the frontier; failed branches stay as evidence, not deleted history.
3. **Externalizes control** — Objectives, protected files, metrics, budgets, and keep/revert rules live in versioned control documents—not inside a single LLM context window.
4. **Evaluates and budgets** — Structured pass/fail/revise decisions and explicit resource limits (time, tokens, graph writes) sit outside the agent.
5. **Optionally overlays a knowledge graph** — Durable claims, sources, and provenance on top of the commit DAG. Graph writes are off by default so agents cannot invent “knowledge” without opt-in.

The demo workspace (`examples/demo_workspace/`) is a tiny CPU trainer: mutate hyperparameters in `train.py`, never touch `prepare.py`, minimize `val_loss`, keep only on real improvement.

## Why this matters for agentic computing

Agentic computing moves beyond one-shot prompts: agents plan, act, observe, and iterate over long horizons. That only works if **verifiability and memory live outside the model**.

Without infrastructure like this, agentic systems tend to:

- **Hallucinate progress** — claiming a better metric without a real run
- **Lose lineage** — no recoverable path from “best result” back to hypothesis, parent commit, and evaluator decision
- **Overwrite the eval surface** — agents “cheat” by editing the test or metric definition
- **Blow budgets** — unbounded tool calls, tokens, or graph writes overnight
- **Confuse work history with domain knowledge** — stuffing everything into one undifferentiated store

This platform treats those failure modes as first-class design constraints (the “Kaparthy correction”): hostile metrics (keeps only from parsed `run_command` stdout), Git as truth, bounded context packs, and KG humility. The central invariant is full traceability:

> objective → plan → artifact → source → graph path → evaluator decision → bounded execution record

That is the difference between a demo that looks smart in a chat transcript and a research loop you can run overnight, audit, recover, and hand to another agent or human.

## Kaparthy correction (must-know)

| Rule | Enforcement |
|------|-------------|
| **Hostile metrics** | `kept` only from real `run_command` stdout parse — `metric_override` always `rejected` |
| **Git is truth** | DAG parents/objects from bare Git; no orphan `register_node` in normal mode |
| **Context pack** | `ah context` / `POST /dag/context` — bounded agent context (`token_accounting: approx_chars_div_4`) |
| **Athlete** | `ah agent-run --loop <id>` heuristic agent (no LLM required) |
| **KG humility** | Graph writes **off** by default on agent path (`--enable-graph-writes` to opt in) |

> A ratchet that cannot be lied to is worth more than a knowledge graph that can be written by anything.

Token estimates use **chars/4** — not a tokenizer; do not bill from them.

## Architecture (four layers)

| Layer | Concern | Package |
|-------|---------|---------|
| 1 Measured Loop | Verifiable iteration + reversibility | `agentic_platform.loops` |
| 2 Commit DAG | Experiment lineage + message board | `agentic_platform.dag` |
| 3 Software 3.0 | Control docs, evaluators, budgets | `control`, `eval`, `runs` |
| 4 Knowledge Graph | Durable knowledge + provenance | `agentic_platform.graph` |

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q
```

Run API:

```powershell
$env:AGENTIC_DATA = ".\data"
agentic-api
```

CLI:

```powershell
ah leaves
ah context --budget-tokens 2000
ah agent-run --loop <loop_id> --max-trials 8
```

Dev agent key: `X-Agent-Key: architect-dev-key`.

## Demo

15–20 min live path (no LLM): bootstrap → athlete → inspect → hostile reject.

```powershell
$env:AGENTIC_DATA = ".\data"
ah demo bootstrap
ah demo athlete --loop <loop_id> --max-trials 8
ah demo hostile --loop <loop_id>
```

Full room script: [docs/demo.md](docs/demo.md). Trainer reference: `examples/demo_workspace/`.

## Phase 5 hardening

| Control | Detail |
|---------|--------|
| Sandbox | Scrubbed child env; `python script.py` allowlist; secret scan on diffs |
| Auth | `X-Agent-Key`; `AGENTIC_REQUIRE_AUTH=1` for production; `POST /auth/keys` |
| Recovery | `POST /loops/{id}/recover` |
| Health | `GET /health`, `GET /ready` |
| CI | `.github/workflows/ci.yml` |

See `docs/runbook.md`.

## ADRs

- `docs/adr/ADR-001-storage-and-runtime.md`
- `docs/adr/ADR-002-phase-scope-sections-1-8.md`
- `docs/adr/ADR-003-git-authoritative-dag.md`
- `docs/adr/ADR-004-kaparthy-correction-exit.md`
- `docs/adr/ADR-005-phase5-hardening.md`
- `docs/adr/ADR-006-phase6-top-slice.md`

## Bibliography

Collected foundational sources and Phase 6 candidate papers: [`docs/bibliography.md`](docs/bibliography.md).

Phase 6 technical plan (work packages 1–6): [`docs/phase6-technical-plan.md`](docs/phase6-technical-plan.md).

## Invariants

See Master Plan §7 — `agentic_platform.invariants`.
