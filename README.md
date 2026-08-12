# Agentic Research Platform (kaparthy)

Production oriented implementation of the **Agentic Research Platform** Master Plan: measured loops, commit DAGs (AgentHub), Software 3.0 control/evaluation/budgets, and a knowledge-graph overlay.
This repo was influenced by a number of papers that read about or from Kaparthy.

**Contract version:** `v0.1.0-frozen` schemas · OpenAPI `0.1.1`  
**Authority:** IT Architect  
**Phase:** 5 complete (integration & hardening) · Phase 6 pilot authorized

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

## Demo workspace

`examples/demo_workspace/` — tiny CPU trainer with mutable `LR`/`STEPS`/`HIDDEN`/`L2`, protected `prepare.py`, living `program.md`.

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

## Bibliography

Collected foundational sources and Phase 6 candidate papers: [`docs/bibliography.md`](docs/bibliography.md).

## Invariants

See Master Plan §7 — `agentic_platform.invariants`.
