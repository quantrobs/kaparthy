# ADR-003: Git-Authoritative Commit DAG

**Status:** Accepted  
**Date:** 2026-07-28  
**Authority:** IT Architect  
**Responds to:** Kaparthy review C2  

## Decision

Bare Git (`hub.git`) is the **sole source of truth for commit topology** (parent edges, object existence). SQLite `commit_nodes` stores **annotations only** (agent, hypothesis, metric, status, board links).

`register_node` requires `git cat-file -t <hash> == commit` unless `AGENTIC_DAG_ALLOW_ORPHAN_META=1` (unit/debug only; forbidden in acceptance tests). On write, parents are recomputed from Git; client-supplied parents that disagree are ignored.

## Consequences

- Multi-agent tests must push real commits.  
- Metadata cannot invent scientific lineages.  
- Slightly more setup in tests; correct science.
