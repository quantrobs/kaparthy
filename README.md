# Agentic Research Platform (kaparthy)

Production-oriented implementation of the **Agentic Research Platform** Master Plan (sections 1–8): measured loops, commit DAGs (AgentHub), Software 3.0 control/evaluation/budgets, and a knowledge-graph overlay.

**Contract version:** `v0.1.0-frozen`  
**Authority:** IT Architect

## Architecture (four layers)

| Layer | Concern | Package |
|-------|---------|---------|
| 1 Measured Loop | Verifiable iteration + reversibility | `agentic_platform.loops` |
| 2 Commit DAG | Experiment lineage + message board | `agentic_platform.dag` |
| 3 Software 3.0 | Control docs, evaluators, budgets | `control`, `eval`, `runs` |
| 4 Knowledge Graph | Durable knowledge + provenance | `agentic_platform.graph` |

## APIs (frozen)

| API | Base path |
|-----|-----------|
| Control Document | `/control` |
| Loop Execution | `/loops` |
| DAG / AgentHub | `/dag` |
| Knowledge Graph | `/graph` |
| Evaluation | `/eval` |
| Budget & Audit | `/runs` |

Schemas: `contracts/v0.1.0/schemas/`  
OpenAPI: `contracts/v0.1.0/openapi.yaml`

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
# or: python -m agentic_platform.api.server
```

CLI (`ah`):

```powershell
ah leaves
ah children <hash>
ah lineage <hash>
ah board
```

Default agent key for local dev: header `X-Agent-Key: architect-dev-key`.

## Acceptance tests (§8)

```powershell
pytest tests/acceptance -q
```

Covers loop reproducibility, crash recovery, protected paths, multi-agent DAG, board restart, claim provenance, reversible entity merge, token-budgeted subgraphs, full audit trail, and budget exhaustion.

## ADRs

- `docs/adr/ADR-001-storage-and-runtime.md`
- `docs/adr/ADR-002-phase-scope-sections-1-8.md`

## Invariants

See Master Plan §7 — enforced in `agentic_platform.invariants`.
