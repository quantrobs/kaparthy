# Live demo — Hostile loop athlete

**Audience:** technical  
**Duration:** ~15–20 minutes  
**Layers exercised:** 1 (measured loop), 2 (DAG / board / context), Kaparthy hostile metrics  
**Not in this script:** full budget/eval audit, knowledge-graph writes, production auth

## Prerequisites

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:AGENTIC_DATA = "D:\kaparthy\data"
# Leave AGENTIC_REQUIRE_AUTH unset for local demo
```

Optional: `pytest -q tests/acceptance/test_demo_bootstrap.py` before the room.

## Room script (DEMO-RUN-001)

| Minute | Action | Show |
|--------|--------|------|
| 0–2 | Env + bootstrap | `loop_id`, baseline `best_metric` |
| 2–8 | Athlete (8 trials) | kept/reverted ledger; optional live `train.py` |
| 8–12 | Leaves / board / context | frontier + bounded context pack |
| 12–16 | Hostile reject | `rejected` / INV-02; best unchanged |
| 16–20 | Show + narrative | Kaparthy quote; what was *not* demoed |

### Commands

```powershell
# 0–2 Bootstrap (creates control doc + loop; seeds trainer)
ah demo bootstrap
# Copy loop_id from JSON. Equivalent: python scripts/demo_bootstrap.py

# 2–8 Heuristic athlete (no LLM)
ah demo athlete --loop <loop_id> --max-trials 8

# 8–12 Inspect lineage and Software 3.0 context
ah leaves
ah board
ah context --budget-tokens 2000

# 12–16 Prove the ratchet cannot be lied to
ah demo hostile --loop <loop_id>
# Longer punchline (also reject prepare.py edit):
# ah demo hostile --loop <loop_id> --also-protected

# 16–20 Operator snapshot
ah demo show --loop <loop_id>
```

## Talking points (must)

1. Keep requires a real `run_command` parse — `metric_override` always rejects (INV-02).
2. Git workspace is reversible; failed trials stay as evidence on the DAG/board.
3. Context pack is bounded (`token_accounting: approx_chars_div_4`).
4. Graph writes are **off** by default (`--enable-graph-writes` to opt in).

> A ratchet that cannot be lied to is worth more than a knowledge graph that can be written by anything.

## Expected outcomes

- Bootstrap returns non-null `best_metric` from baseline `python train.py`.
- Athlete completes N trials with statuses `kept` / `reverted` / rarely `crash`.
- Improvement is **likely but not guaranteed** — demo the ledger, not a magic metric drop.
- Hostile step: `passed: true`, `best_unchanged: true`, error contains `INV-02`.

## Non-promises

- Overnight daemon / wall-clock scheduler
- Guaranteed `val_loss` drop
- LLM intelligence (athlete is a hyperparameter grid)
- Production auth (`AGENTIC_REQUIRE_AUTH=1` — see [runbook.md](runbook.md))

## Failure recovery

Dirty workspace or mid-trial crash:

```http
POST /loops/{id}/recover
```

Or in Python: `platform.loops.recover(loop_id)` — resets to `best_commit`, re-runs metric.

## Follow-on (deferred)

Four-layer audit (control → budget → run → trials → DAG → graph → eval → audit):  
`tests/acceptance/test_section8_e2e.py`.
