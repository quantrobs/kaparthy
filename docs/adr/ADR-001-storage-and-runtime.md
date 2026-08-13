# ADR-001: Storage and Runtime Choices

**Status:** Accepted  
**Date:** 2026-07-28  
**Authority:** IT Architect  

## Context

Phase 1+ requires durable storage for Control Documents, Trials, Commit DAG metadata, message board posts, Knowledge Graph nodes/edges, Evaluations, BudgetDeclarations, and Runs. Contracts are frozen as `v0.1.0-frozen`.

## Decision

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Service runtime | Python 3.11+, FastAPI | Fast schema validation, small team velocity |
| Metadata store | SQLite (single file per deployment) | Matches AgentHub sketch; zero-ops; testable |
| Commit DAG | Bare Git repository | DAG *is* the graph; fetch/checkout native |
| Artifact plane | Content-addressed filesystem under `data/artifacts/` | Immutable blobs; simple recovery |
| Knowledge graph | SQLite tables + in-process adjacency | Provenance-first; reversible entity resolution |
| Schema validation | `jsonschema` against `contracts/v0.1.0/schemas` | Frozen contract enforcement |
| Auth | Per-agent API key header `X-Agent-Key` | AgentHub model; sandbox later |
| CLI | `ah` entrypoint via Typer | Graph interface: push/fetch/children/leaves/lineage/diff |

## Consequences

- Single-node first; multi-node requires later ADR for shared Git object store.
- SQLite serializes writers; acceptable for pilot scale.
- Any contract change requires `v0.1.1+` and a new ADR.

## Alternatives Rejected

- PostgreSQL (premature ops cost)
- Collapsing KG into Git notes (query/performance mismatch)
- Rewriting history on revert (violates invariant 8)
