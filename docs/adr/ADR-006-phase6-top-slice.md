# ADR-006: Phase 6 Work Packages 1–6

**Status:** Accepted  
**Date:** 2026-08-12  
**Authority:** IT Architect  
**Responds to:** `docs/bibliography.md` items 1–6 (C6/C7, C4, C1/C3, C13, C12, C8)  
**Companion:** `docs/phase6-technical-plan.md`

## Context

Phase 5 is complete. The ratchet cannot be lied to with `metric_override`, but a keep is still one parsed scalar against last-best. `propose_trial` always resets to `loop.best_commit`, and the simple agent only pushes kept commits, so the DAG is a line. Context pack is a dump. `subgraph()` is BFS over an empty graph on the agent path.

## Decision

Authorize and sequence six work packages. Implementation order: **6 → 1 → 2 → 3 → 4 → 5**. A package may not merge before its gate.

| WP | Bibliography | Decision | Gate |
|----|--------------|----------|------|
| **6** | C8 standing release gates | **Build now.** Named pytest marker + CI job. | None |
| **1** | C6 PACE + C7 sealed holdout | **Build now.** Keep is a sealed certificate. | WP6 marker exists |
| **2** | C4 SemDeDup | **Build now.** Frontier filter before commit. | WP1 contracts on master (tests may overlap) |
| **3** | C1/C3 leaf search, heuristic | **Build now.** Optional parent; always-push evidence; no LLM. | WP1 merged |
| **4** | C13 GraphRAG leaf summaries | **Planned.** Template briefing of leaf clusters. Not Claims. | WP3 produces >1 leaf |
| **5** | C12 GraphFlow retrieval | **Planned.** System lineage projector + diversity walk. | WP1 merged; agent KG writes stay **off** |
| — | C9 SEA, C14 KG²RAG, W2–W6, D1–D5 | Unchanged: deferred or declined. | — |

Keep vs. **global** best (INV-02) does not change when WP3 parents from a non-best leaf. WP5 may project Commit/Metric/Evaluation nodes as `system-projector`. It may not project Claims and does not flip `--enable-graph-writes`.

## Contract

`v0.1.0-frozen` remains the accepted baseline. WP1 introduces additive `contracts/v0.1.2/` (OpenAPI `0.1.2`). Old payloads without the new optional fields must still validate. WP4–5 add optional context-pack / subgraph fields only.

## Invariants

No change to INV-01–12. WP1 tightens INV-02 (sealed instance set). WP5 must still honor INV-12 (bounded subgraph) and INV-05 (no sourceless Claims from the projector).

## Consequences

- Demo `SEED` is no longer an agent-visible keep lever.
- Context pack and `program.md` strip sealed seeds.
- Existing §8 tests stay green under `keep_gate.mode = single_shot`.
- `pytest -m release_gate` is the merge valve for WP1–5.
- The only legal skip in the 1–6 sequence is WP4 v2 (LLM rewrite of the template).

## Alternatives rejected

- Shipping an LLM experiment-manager before the keep gate (W1).
- Turning on agent KG writes so GraphFlow has data (use a system projector instead).
- Treating community summaries as Claims.
- Comparing keep against the trial's parent metric (breaks the ratchet).
- Embedding-only dedup as WP2 v1.
- Deleting overlapping §8 tests once release gates exist.
