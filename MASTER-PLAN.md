# Agentic Research Platform — Master Plan

**Document Status:** Authoritative  
**Version:** 1.0  
**Date:** 2026-07-28  
**Owner:** IT Architecture  
**Approval Model:** IT Architect decides; executive decisions are logged and final  

---

## 1. Vision

Build a production-grade agentic research platform that externalizes iteration, lineage, control, and durable knowledge into four explicit, composable layers—measured loops, commit DAGs, Software 3.0 control surfaces, and a knowledge-graph overlay—so that every important output is traceable to an objective, a plan, an artifact, a source, a graph path, an evaluator decision, and a bounded execution record. The system must remain operable by a small team, recoverable from partial failure, and evolvable without rewriting the core invariants.

---

## 2. Background and Source Material

This plan synthesizes:

- The independent “Graph Engineering” technical note (July 2026) mapping Karpathy’s autoresearch → AgentHub progression onto Anthropic’s workflow patterns and Knowledge Graph Cookbook.
- Primary Karpathy sources:
  - `karpathy/autoresearch` (GitHub, March 2026) — measured single-agent research loop.
  - AgentHub (sketch + public forks) — agent-first commit DAG + message board.
  - Sequoia AI Ascent 2026 fireside chat + Karpathy’s own summary (“Software 3.0, Agentic Engineering, and Jagged Intelligence”).
  - Key blog posts: “Verifiability” (Nov 2025), “Animals vs Ghosts” (Oct 2025), 2025 LLM Year in Review.
- Detailed chapter specifications (Chapters 1–8) produced for architectural decomposition.
- IT Architect derivations: interface contracts, data models, invariants, acceptance tests, and phased roadmap.
- Frozen API contracts `v0.1.0-frozen` (OpenAPI + JSON Schemas).

The annotated, layer-mapped collection of these sources plus Phase 6 candidate papers lives in [`docs/bibliography.md`](docs/bibliography.md). That file does not override this plan.

---

## 3. Architecture Overview

### 3.1 Four Layers

| Layer | Name                        | Primary Concern                          | Key Artifact                  |
|-------|-----------------------------|------------------------------------------|-------------------------------|
| 1     | Measured Loop               | Verifiable iteration + reversibility     | `program.md` + Git + ledger   |
| 2     | Commit DAG (AgentHub)       | Experiment lineage + multi-agent frontier| Bare Git + SQLite + CLI       |
| 3     | Software 3.0 Framing        | Explicit control, evaluation, budgets    | Control Document + evaluators |
| 4     | Knowledge-Graph Overlay     | Durable domain knowledge + provenance    | Typed property graph          |

### 3.2 Five-Plane Reference Architecture

1. **Control Plane** — objectives, plans, budgets, termination.
2. **Execution Plane** — isolated runs of tools, training jobs, sub-agents.
3. **Artifact Plane** — immutable versioned blobs (code, reports, metrics, evaluations).
4. **Graph Plane** — commit DAG + knowledge graph + cross-links.
5. **Evaluation Plane** — deterministic checks, model evaluators, human gates.

### 3.3 Central Invariant (Traceability)

Every important output must be reconstructible to:

> objective → plan → artifact → source → graph path → evaluator decision → bounded execution record

---

## 4. Layer Specifications (Summary)

### Layer 1 — Measured Loop (Autoresearch Mechanics)

- Immutable evaluation surface (`prepare.py` equivalent).
- Mutable experimental surface (`train.py` equivalent).
- Natural-language control program (`program.md`).
- Ratchet: inspect → propose → commit → evaluate → keep/revert → log.
- Short fixed time budget, reversible Git state, append-only ledger.
- Invariants: protected files never modified; every kept commit improves the declared metric; working tree always left runnable.

### Layer 2 — AgentHub DAG Operations

- Bare Git repository (DAG is the graph).
- SQLite for metadata + message board.
- CLI/HTTP surface: `push`, `fetch`, `children`, `leaves`, `lineage`, `diff`, board posts.
- No required main branch; leaves are the frontier; failed experiments remain evidence.
- Explicitly a sketch; production needs compaction, stronger auth, semantic deduplication.

### Layer 3 — Software 3.0 Framing

- Software 1.0 = specifiability; Software 2.0 = verifiability; Software 3.0 = context window as programmable interface.
- Vibe coding raises the floor; agentic engineering raises the ceiling.
- LLMs are “ghosts” (statistical distillations), not “animals”.
- Control, evaluation, and memory must live outside any single context window.
- Explicit budgets and structured evaluation are mandatory.

### Layer 4 — Knowledge Graph on Commit DAG

- Complementary, not collapsed: DAG = work lineage; KG = domain knowledge.
- Node types: Entity, Claim, Source, Artifact, AgentRun, Evaluation, Commit, Metric.
- Edge types: PARENT_OF, PRODUCED, SUPPORTS, CONTRADICTS, ABOUT, EVALUATED_BY, SUPERSEDES, RESOLVED_TO, …
- Context construction: resolve entities → expand 1–2 hops → prioritize verified claims → serialize under token budget → attach stable edge IDs.
- All writes are versioned, provenance-carrying, and reversible (especially entity resolution).

---

## 5. Frozen Interface Contracts

**Location:** `/home/workdir/artifacts/contracts/v0.1.0/`  
**Status:** FROZEN as `v0.1.0-frozen` (2026-07-28)

### APIs

| API                  | Base Path   | Purpose                                      |
|----------------------|-------------|----------------------------------------------|
| Control Document     | `/control`  | Versioned objectives & loop policy           |
| Loop Execution       | `/loops`    | Measured ratchet lifecycle                   |
| DAG / AgentHub       | `/dag`      | Commit DAG + message board                   |
| Knowledge Graph      | `/graph`    | Typed graph + bounded subgraph retrieval     |
| Evaluation           | `/eval`     | Structured pass/fail/revise decisions        |
| Budget & Audit       | `/runs`     | Run handles, budgets, full audit trail       |

### JSON Schemas (authoritative)

- `control-document.schema.json`
- `trial.schema.json`
- `commit-node.schema.json`
- `graph-update.schema.json`
- `evaluation-result.schema.json`
- `budget-declaration.schema.json`
- `run.schema.json`

**Rules**
- No implementation PR may violate these contracts.
- Any change requires a new version + Architecture Decision Record.
- All services must validate against the published schemas.

---

## 6. Data Models (Core)

- **ControlDocument** — objective, protected paths, metric definition, comparison function, run command, time budget, keep/escalation/exhaustion criteria.
- **Trial** — commit hash, parent, agent, hypothesis, metric, status (kept/reverted/crash), wall time.
- **CommitNode** — hash, parents, agent, hypothesis, metric, status, bundle metadata.
- **GraphUpdate** — nodes[], edges[], run_id, agent_id (with full provenance).
- **EvaluationResult** — decision (pass/fail/revise), target, rubric, evidence edges, required fixes, confidence.
- **BudgetDeclaration** — max model calls, sub-agents, tokens, wall-clock, cost, graph writes.
- **Run** — control doc link, budgets, status, consumed resources, audit log URI.

---

## 7. Invariants (Non-Negotiable)

1. Evaluation surface is never modified by agents.
2. Every kept commit satisfies the comparison function in the active Control Document.
3. Working tree / execution environment is always left runnable after revert.
4. Results ledger and Git history are append-only for kept trials.
5. Every Claim has ≥1 Source or is explicitly marked inference.
6. Every Artifact has an authoring AgentRun and a version.
7. Every Evaluation references a concrete rubric.
8. Superseded objects remain addressable; history is never rewritten.
9. Entity-resolution decisions are additive and reversible.
10. Traceability invariant holds for every important output.
11. No run may exceed its declared BudgetDeclaration.
12. Context supplied to any agent is a bounded subgraph only.

---

## 8. Acceptance Tests (Gate Criteria)

**Loop**
- After 50 autonomous trials the current-best metric is reproducible from commit hash alone.
- Crash mid-training → revert + ledger entry; next trial resumes from last kept state.
- Attempt to edit protected path is rejected before commit.

**DAG**
- Three concurrent agents can push divergent children; `leaves` and `children` return correct sets.
- Any commit is fetchable and check-out-able.
- Message-board posts survive restart.

**Knowledge Graph**
- Claim traces to supporting commits and sources.
- False entity merge is reversible.
- Subgraph retrieval respects token budget.

**End-to-End**
- Full audit trail reconstructs objective → plan → runs → commits → claims → evaluations → budgets.
- Budget exhaustion returns structured partial result, never silent truncation.

---

## 9. Phased Implementation Roadmap

| Phase | Name                          | Duration   | Exit Criteria                                      | Status      |
|-------|-------------------------------|------------|----------------------------------------------------|-------------|
| 0     | Foundations                   | 1–2 weeks  | Contracts frozen, auth + audit skeleton live       | **Complete**|
| 1     | Measured Loop                 | 2–3 weeks  | All Loop acceptance tests green                    | **Complete**|
| 2     | DAG Collaboration             | 2–3 weeks  | Multi-agent DAG tests green                        | **Complete**|
| 3     | Evaluation Plane & Budgets    | 1–2 weeks  | Traceability + budget enforcement green            | **Complete**|
| 4     | Knowledge-Graph Overlay       | 3–4 weeks  | Graph acceptance tests green                       | **Complete**|
| 4.5   | Honesty & Athlete (Kaparthy)  | 1 wave     | Hostile metrics, Git-truth DAG, agent, context pack| **Complete**|
| 5     | Integration & Hardening       | 2–3 weeks  | Full E2E + security + recovery under load          | **Complete**|
| 6     | Production Pilot              | Ongoing    | Real workload metrics + runbooks                   | Authorized  |

**Rules**
- No phase may start until the previous phase’s exit criteria are met.
- Every phase produces an Architecture Decision Record for any deviation from frozen contracts.

---

## 10. Decision Log

| Date       | Decision                                                                 | Authority          |
|------------|--------------------------------------------------------------------------|--------------------|
| 2026-07-28 | Architecture approved subject to contract freeze                         | IT Architect       |
| 2026-07-28 | Approval model changed: IT Architect decides; executive decisions final  | Executive          |
| 2026-07-28 | OpenAPI + JSON Schemas frozen as `v0.1.0-frozen`                         | IT Architect       |
| 2026-07-28 | Phase 0 complete; Phase 1 (Measured Loop) authorized                     | IT Architect       |
| 2026-07-28 | ADR-001 storage (SQLite + bare Git + content-addressed artifacts)        | IT Architect       |
| 2026-07-28 | ADR-002 sections 1–8 vertical build authorized non-stop                  | IT Architect       |
| 2026-07-28 | Phases 1–4 implemented; §8 acceptance suite is the gate                  | IT Architect       |
| 2026-07-28 | Kaparthy review accepted as correction authority (C1–C12)                | IT Architect       |
| 2026-07-28 | metric_override cannot produce kept trials                               | IT Architect       |
| 2026-07-28 | Git authoritative for DAG topology; SQLite annotations only (ADR-003)    | IT Architect       |
| 2026-07-28 | Additive context pack API; OpenAPI 0.1.1                                 | IT Architect       |
| 2026-07-28 | Heuristic simple agent required before Phase 5; KG writes default off    | IT Architect       |
| 2026-07-28 | Phase 4.5 complete; Phase 5 authorized (not auto-started)                | IT Architect       |
| 2026-07-28 | Phase 5: sandbox, auth keys, WAL locks, recover API, CI, runbook (ADR-005)| IT Architect       |
| 2026-07-28 | Metric parse uses last regex match (anti fake-print cheat)               | IT Architect       |
| 2026-07-28 | Phase 5 complete; Phase 6 production pilot authorized                    | IT Architect       |
| 2026-08-12 | Collected bibliography committed at `docs/bibliography.md`               | IT Architect       |
| 2026-08-12 | ADR-006 Phase 6 top slice (sealed keep, frontier filter, leaf search)    | IT Architect       |

---

## 11. Current Status & Immediate Next Actions

**Status:** Phase **5 (Integration & Hardening)** complete per ADR-005. Sandbox, secret scan, auth, recovery, concurrent SQLite, CI, and runbook are live. Phase 6 (production pilot) is **authorized**.

**Immediate Actions**

1. **Ops** — Run a real pilot workload with `AGENTIC_REQUIRE_AUTH=1` and rotated admin token.  
2. **Architect** — Execute ADR-006 Wave A (sealed keep-gate) before any LLM proposer; then B (dedup) and C (leaf search). Pilot metrics: keep rate, crash rate, budget exhaustion rate, recovery success, leaves/kept, duplicate-reject rate.  
3. **Security** — Optional P3: cgroups / network namespace (out of process scope until pilot demands it).

**Single most important action right now**  
Implement Wave A (`docs/phase6-technical-plan.md`): a keep is a sealed certificate, not one lucky seed. Do not relax sandbox or keep-path rules.

---

## 12. References

- Graph Engineering technical note (independent synthesis, July 2026).
- Karpathy, A. — autoresearch repository (March 2026).
- Karpathy, A. — AgentHub sketch + public forks.
- Karpathy, A. — Sequoia AI Ascent 2026 summary (April 2026).
- Karpathy, A. — “Verifiability”, “Animals vs Ghosts”, 2025 LLM Year in Review (Bear blog).
- Anthropic — Building Effective Agents (2024), Dynamic Workflows (2026), Knowledge Graph Construction Cookbook.
- Frozen contracts: `/home/workdir/artifacts/contracts/v0.1.0/`.

Annotated collection, layer mapping, steal / do-not-steal notes, and Phase 6 candidates: [`docs/bibliography.md`](docs/bibliography.md).

Prioritized engineering plan for the candidates that floated: [`docs/phase6-technical-plan.md`](docs/phase6-technical-plan.md) (ADR-006).

---

**End of Master Plan**  
This document is the single source of truth for vision, architecture, contracts, invariants, tests, and roadmap. All subsequent work must align with it.
