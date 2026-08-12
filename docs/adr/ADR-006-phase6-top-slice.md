# ADR-006: Phase 6 Top Slice — Honest Keep, Frontier Filter, Leaf Search

**Status:** Accepted  
**Date:** 2026-08-12  
**Authority:** IT Architect  
**Responds to:** `docs/bibliography.md` candidates C6, C7, C8, C10, C4, C1, C3  
**Companion:** `docs/phase6-technical-plan.md`

## Context

Phase 5 is complete. The ratchet cannot be lied to with `metric_override`, but a keep is still **one** parsed scalar against last-best. `propose_trial` always resets to `loop.best_commit`, and the simple agent only pushes **kept** commits, so the AgentHub DAG is a line, not a frontier. Bibliography scoring against the live code is in the technical plan.

## Decision

Authorize a three-wave Phase 6 top slice. No other bibliography candidate is authorized to start until its wave's predecessor exits.

| Wave | Bibliography | Decision |
|------|--------------|----------|
| **A** | C6 PACE + C7 sealed holdout + C8/C10 gates | **Build.** Keep becomes a paired, sealed, anytime-valid (or majority-of-seeds) certificate. Standing adversarial tests ship in the same wave. |
| **B** | C4 SemDeDup | **Build.** Frontier filter before commit. Git history is never rewritten. |
| **C** | C1/C3 leaf search, heuristic only | **Build.** Optional `parent_commit` on trials; push reverted/evidence commits; propose from leaves. No LLM. |
| — | C13 leaf summaries | Deferred until A–C green. Template summaries only; no KG writes. |
| — | C12 GraphFlow, C9 SEA, C14 KG²RAG | Deferred. KG writes stay **off**. |
| — | W2–W6 skill-library line | Out of scope. Sibling product. |
| — | D1–D5 | Still declined. |

## Contract

`v0.1.0-frozen` remains the accepted baseline. Wave A introduces **additive** `contracts/v0.1.2/` (OpenAPI `0.1.2`). Old payloads without the new optional fields must still validate. `additionalProperties: false` is preserved; new fields are named, optional, and default to today's single-shot keep.

## Invariants

No change to INV-01–12. Wave A **tightens** INV-02 (a keep must satisfy the comparison on the sealed instance set, not one lucky seed). Wave C does **not** change the keep baseline: exploration may parent from any leaf; keep still beats the **global** best metric.

## Consequences

- Demo `SEED` is no longer an agent-visible keep lever: the eval harness injects sealed seeds at run time.
- Context pack and `program.md` must strip sealed seeds (C7).
- Existing §8 loop tests stay green under `keep_gate.mode = single_shot` (default).
- New acceptance tests in `tests/acceptance/test_phase6_*.py` are the wave gates.

## Alternatives rejected

- Shipping an LLM experiment-manager before the keep gate (repeats AI Scientist failure modes; W1).
- Turning on KG writes to “make context better” (bibliography §6).
- Embedding-only dedup as Wave B v1 (hparams + normalized diff hash is enough for the demo trainer).
- Comparing keep against the trial's parent metric instead of global best (breaks the ratchet).
