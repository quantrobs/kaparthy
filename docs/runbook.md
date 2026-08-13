# Operations Runbook — Agentic Research Platform

**Phase:** 6 (sealed keep-gate, frontier filter, leaf search)  
**Contract:** `v0.1.2` schemas · OpenAPI `0.1.2` (v0.1.0 documents still validate)

## Start / stop

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:AGENTIC_DATA = "D:\kaparthy\data"
$env:AGENTIC_REQUIRE_AUTH = "1"          # production
$env:AGENTIC_ADMIN_TOKEN = "<long-random>"
$env:AGENTIC_REJECT_UNKNOWN_KEYS = "1"
agentic-api
```

Health:

- `GET /health` — process up + dependency checks  
- `GET /ready` — 503 if degraded  

## Agent keys

```http
POST /auth/keys
X-Admin-Token: <admin>
{"agent_id": "researcher-7"}
```

Clients send `X-Agent-Key: <key>` on every mutating/read API call when `AGENTIC_REQUIRE_AUTH=1`.

List fingerprints (not raw keys): `GET /auth/agents`.

Dev default key (local only): `architect-dev-key` for agent `architect`.

## Loop recovery

After crash or dirty workspace:

```http
POST /loops/{id}/recover
```

Resets working tree to `best_commit`, re-runs metric, returns `metric_ok` / `matches_best`.

## Sealed keep-gate

Declare `keep_gate.mode: paired_pace` plus sealed `seeds` on the control document for overnight pilots. Seeds never appear in `program.md` or the context pack. Default remains `single_shot` so existing §8 tests stay green.

## Release gates

A release is `pytest -m release_gate` green plus `GET /ready`. See `docs/release-gates.md`.

## Sandbox policy

| Control | Behavior |
|---------|----------|
| `run_command` | Allowlist: `python[3] [-u] <script.py>`; no shell chaining |
| Env scrub | Child process loses `*KEY*`, `*SECRET*`, `*TOKEN*`, cloud creds |
| Diff scan | Rejects AWS keys, GitHub PATs, private key blocks, etc. |
| Override | `AGENTIC_ALLOW_ARBITRARY_RUN_CMD=1` only for trusted operators |

## Failure modes

| Symptom | Action |
|---------|--------|
| Trials all `crash` / metric not found | Check `run_command`, Python path, `program.md` |
| All `rejected` secret patterns | Remove tokens from edits; rotate leaked keys |
| `budget_exhausted` | Read `partial_result`; raise budget or stop |
| DAG `commit not in bare Git` | Push real commits; never invent hashes |
| `/ready` 503 | Inspect `db` / `hub` / `schemas` fields on `/health` |
| All `rejected` `duplicate_of` | Distinct structural edit or new hparams required |

## Backup

1. Stop writers.  
2. Copy `AGENTIC_DATA/platform.db` (+ `-wal`/`-shm` if present).  
3. Copy `AGENTIC_DATA/hub.git` and `artifacts/`.  
4. Verify with fresh `AGENTIC_DATA` restore + `pytest` smoke.

## Security checklist (pilot)

- [ ] `AGENTIC_REQUIRE_AUTH=1`  
- [ ] `AGENTIC_ADMIN_TOKEN` set and not committed  
- [ ] Dev key revoked or unused in shared env  
- [ ] Workspaces on isolated volume  
- [ ] No secrets in `program.md` or board posts  
- [ ] `keep_gate.seeds` never pasted into `program.md`  
