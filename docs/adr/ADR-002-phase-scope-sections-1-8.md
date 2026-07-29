# ADR-002: Build Scope for Sections 1–8

**Status:** Accepted  
**Date:** 2026-07-28  
**Authority:** IT Architect  

## Context

Master Plan sections 1–8 define vision through acceptance tests. User directive: build non-stop; Architect owns all approvals.

## Decision

Implement a **vertical slice of all four layers** and **all six APIs** against `v0.1.0-frozen`, with automated acceptance tests for Loop, DAG, KG, and E2E criteria from §8. Phase roadmap gates (Phase 1→2→3→4) are collapsed for this build only because Architect authorizes concurrent delivery of the contract surface; production hardening (Phase 5) remains deferred.

## Deliverables

1. Frozen contracts under `contracts/v0.1.0/`
2. Measured loop with protected-path enforcement, ratchet, ledger, crash recovery
3. AgentHub DAG + message board
4. Evaluation plane + budget enforcement
5. Knowledge graph with reversible entity resolution and token-budgeted subgraph retrieval
6. Full audit trail reconstructing objective → plan → runs → commits → claims → evaluations → budgets

## Out of Scope (deferred)

- Multi-tenant auth / OIDC
- Distributed bare-repo replication
- Production load / security hardening
- Real GPU training jobs (demo uses synthetic metrics)
