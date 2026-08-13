# ADR-005: Phase 5 Integration & Hardening

**Status:** Accepted  
**Date:** 2026-07-28  
**Authority:** IT Architect  

## Decision

Phase 5 hardens **evaluation boundaries and operability** before multi-tenant scale:

1. **Sandbox** — scrubbed env, run_command allowlist, secret scan on diffs, last-match metric parse.  
2. **Auth** — per-agent keys; optional `AGENTIC_REQUIRE_AUTH`; reject unknown keys by default in AuthService; admin key minting.  
3. **Concurrency** — SQLite `RLock` + WAL + busy_timeout.  
4. **Recovery** — `POST /loops/{id}/recover` resets to best commit.  
5. **Observability** — `/health` and `/ready` with dependency checks.  
6. **CI** — GitHub Actions pytest on 3.11/3.12.  

## Non-goals (still deferred)

- gVisor / cgroups / full network namespace isolation  
- OIDC / multi-tenant RBAC  
- Distributed SQLite or multi-node bare Git  

## Exit criteria

- Phase 5 acceptance tests green  
- Existing §8 + 4.5 suites still green  
- Runbook published  
