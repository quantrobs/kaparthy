# Phase 6 Technical Plan — Top Slice

**Status:** Authoritative for Phase 6 engineering  
**Date:** 2026-08-12  
**Authority:** IT Architect  
**ADR:** [ADR-006](adr/ADR-006-phase6-top-slice.md)  
**Literature:** [bibliography.md](bibliography.md)

This plan is what floats to the top after scoring the collected papers against the **live** Phase-5 code, not against a wish list. It does not change INV-01–12. Implementation of Wave A requires `contracts/v0.1.2/` (additive). Waves B and C may land on 0.1.2 fields or on existing `rejected` / board surfaces.

---

## 1. Scoring: why these three, in this order

Criteria (1–10): **integrity** (hostile keep / Git-as-truth), **pilot ROI** (keep rate, crash rate, wasted trials on a real overnight run), **contract cost**, **LLM required**.

| Rank | IDs | Change | Integrity | Pilot ROI | Contract | LLM | Why it floated |
|------|-----|--------|-----------|-----------|----------|-----|----------------|
| **1** | C6 + C7 + C8 + C10 | Sealed paired keep-gate + standing adversarial suite | 10 | 9 | Medium | No | Keep is one noisy `val_loss` vs last best (`loops/service.py` `require_metric_improvement`). Last-match parse stops fake prints, not lucky seeds or self-authored verifiers. |
| **2** | C4 | Frontier dedup before commit | 7 | 8 | Low | No | Master Plan §4.2 already named this. The grid agent already re-touches colliding hparams and force-appends `# agent touch N`. |
| **3** | C1 + C3 (heuristic) | Leaf-parented search + surprise board | 6 | 8 | Low | No | `propose_trial` always `reset_hard(best_commit)`. Simple agent only `dag.push`es **kept** nodes. The DAG cannot be a frontier until both change. |
| 4 | C13 | Leaf-cluster briefing in context pack | 5 | 6 | Low | No | Useful after A–C produce more than one leaf. |
| — | C12 GraphFlow | Query-relevant KG walk | 4 | 3 | Medium | Maybe | KG writes are off. Do not build a retriever for an empty graph. |
| — | C1 LLM manager / C2 writing | Full AI Scientist | 3 | 5 | None | Yes | W1: 42% failed experiments, hallucinated numbers. Blocked on Wave A. |
| — | W2–W6 / C9 / C14 | Skill library, SEA, KG²RAG | — | — | High | Yes | Wrong product. Stay humble. |

**Default-off remains law:** `--enable-graph-writes` stays off until Wave A is green.

---

## 2. What the code does today (the holes)

```text
propose_trial
  reset_hard(loop.best_commit)          # no other parent
  apply edits / reject protected
  commit
  run_sandboxed(run_command) ONCE
  parse LAST regex match
  keep if strictly_better(best_metric)  # one scalar
  else revert

SimpleLoopAgent
  grid LR × STEPS × HIDDEN × L2
  parent = best only
  dag.push only if status == kept       # line, not tree
```

| Hole | File | Effect |
|------|------|--------|
| Single-shot keep | `loops/service.py` `_run_and_parse_metric` + `require_metric_improvement` | One seed, one parse, keep. |
| `SEED` is mutable | demo `train.py`; `mutable_paths: train.py` | Agent can lock the eval seed. |
| Sealed values leak | `dag/service.py` `build_context_pack` dumps control JSON | Future holdout seeds would be visible. |
| No parent choice | `propose_trial` | Cannot implement AgentHub leaves. |
| Evidence not pushed | `simple_loop_agent.py` | Reverts vanish from the hub. |
| Near-duplicate commits | `_propose_edit` comment bump | Frontier fills with no-ops. |

---

## 3. Wave A — Honest keep (C6, C7, C8, C10)

**Goal:** A `kept` trial is a **certificate** over a sealed instance set the agent cannot see or author. Existing single-shot keep remains the default so §8 stays green.

### 3.1 Keep-gate (target behavior)

`ControlDocument.keep_gate` (optional):

```json
{
  "mode": "paired_pace",
  "n_min": 3,
  "n_max": 8,
  "alpha": 0.05,
  "lambda": 0.4,
  "seeds": [17, 23, 41, 59, 67],
  "seed_env": "AGENTIC_EVAL_SEED"
}
```

| Field | Rule |
|-------|------|
| `mode` | `single_shot` (default, today's behavior) or `paired_pace`. |
| `seeds` | **Sealed.** Never rendered into `program.md`, context pack, board posts, or trial `hypothesis`. |
| Eval injection | Harness sets `AGENTIC_EVAL_SEED` (or equivalent) **at run time**. Do not commit seed rewrites. Agent-written `SEED = …` in `train.py` is ignored when `keep_gate.mode = paired_pace`. |
| Paired instances | For each seed: run **incumbent** (`best_commit`) and **candidate** (trial commit) with the same injected seed; parse last-match metric both times. |
| PACE e-process | Start wealth `W=1`. On each pair, if candidate wins the Control Document comparison, `W ← W(1+λ)`, else `W ← W(1-λ)`. |
| Keep | `W > 1/alpha` and at least `n_min` pairs. |
| Revert | `n_max` reached without keep, **or** wealth cannot reach `1/alpha` even if all remaining pairs win (early stop). |
| Fallback v1 | If e-process lands later: keep iff candidate is strictly better on **≥ ceil(n_min/2)+1** sealed seeds **and** better on the mean. Ship the majority rule first only if the e-process slips; do not ship single-shot as `paired_pace`. |

Demo `train.py` must read seed from `os.environ.get("AGENTIC_EVAL_SEED", SEED)` so injection works without editing committed files.

### 3.2 Contract (`v0.1.2`, additive)

New optional properties. `additionalProperties: false` stays. Old documents remain valid.

**`control-document.schema.json`**

- `keep_gate` object: `mode`, `n_min`, `n_max`, `alpha`, `lambda`, `seeds`, `seed_env`.

**`trial.schema.json`**

- `keep_certificate` object (nullable): `mode`, `n_pairs`, `wins`, `losses`, `e_value` (wealth), `alpha`, `mean_incumbent`, `mean_candidate`, `early_stopped`.
- `parent_commit` already exists. Wave C uses it as a **chosen** parent, not only `best_commit`.

**`evaluation-result.schema.json`**

- `e_value`, `n_instances`, `sealed: true`, `pair_summary` (no raw seeds).

**OpenAPI** `0.1.2` — document `keep_gate` on POST `/control` and `keep_certificate` on trial responses. No new required endpoints.

Pydantic models in `models/schemas.py` must match. `ControlService.render_program` **strips** `keep_gate.seeds`.

### 3.3 Code touch list

| Path | Change |
|------|--------|
| `contracts/v0.1.2/` | Copy v0.1.0; add optional fields. Point `core/validation.py` at 0.1.2. |
| `models/schemas.py` | `KeepGate`, `KeepCertificate`; optional on Control/Trial/Eval. |
| `loops/service.py` | `_evaluate_paired(ctl, incumbent_hash, candidate_hash)` → certificate; keep/revert from certificate when mode is `paired_pace`. |
| `eval/service.py` | Persist certificate as `EvaluationResult` (`sealed=true`, no seeds in `notes`). |
| `dag/service.py` `build_context_pack` | Redact `keep_gate.seeds`. Keep `protected_paths` first. |
| `control/service.py` | Redact seeds from `program.md`. |
| `examples/demo_workspace/train.py` | Honor `AGENTIC_EVAL_SEED`. |
| `invariants/checks.py` | `require_sealed_keep(certificate)` — keep forbidden if `sealed` is false in `paired_pace` mode. |
| `tests/acceptance/test_phase6_keep_gate.py` | Wave A gate (below). |
| `tests/acceptance/test_section8_loop.py` | Unchanged; default mode is `single_shot`. |

### 3.4 Standing gates (C8 + C10) — same wave, tests only

These are falsifiable release gates, not features.

| Test | Must fail the cheater |
|------|------------------------|
| `test_metric_override_cannot_keep` | Already exists. Keep. |
| `test_fake_print_uses_last_match` | Prepend `val_loss=0.0`; last real number wins. |
| `test_protected_path_rejected_before_commit` | Already exists. |
| `test_seed_not_in_context_or_program` | `paired_pace` control; seeds absent from pack text and `program.md`. |
| `test_lucky_single_seed_does_not_keep` | Candidate better on 1/n seeds, worse on the rest → `reverted`, certificate present. |
| `test_keep_writes_certificate` | A keep under `paired_pace` has `e_value` or win-count and `sealed`. |
| `test_agent_cannot_author_holdout` | File edit that adds `keep_gate` / `prepare.py` / eval seeds → `rejected`. |

INV checks still run on every keep.

### 3.5 Exit criteria (Wave A)

- [ ] `contracts/v0.1.2/` published; v0.1.0 fixtures still validate.
- [ ] Default `single_shot` keeps all existing §8 + Phase 4.5 + Phase 5 tests green.
- [ ] `paired_pace` keep requires sealed pairs; seeds never appear in agent-visible surfaces.
- [ ] Adversarial suite above is green.
- [ ] Runbook: how to declare `keep_gate` on a pilot control document.

**Do not build in Wave A:** LLM judge, self-review, changing `comparison.function` semantics, cgroups.

---

## 4. Wave B — Frontier filter (C4)

**Goal:** Near-duplicate proposals die **before** Git commit. History stays append-only (INV-08).

### 4.1 v1 fingerprint (no embeddings)

For a proposed `train.py` (and any other mutable file):

1. Parse `NAME = value` assignments for the demo hparam set (`LR`, `STEPS`, `HIDDEN`, `L2`).
2. Strip comments and the parsed lines; SHA-256 the remainder (structural diff).
3. Fingerprint = `hparams_tuple || structural_hash`.

Before `git.commit` in `propose_trial`:

- Look up fingerprint in `trial_fingerprints` (new SQLite table) for this `control_document_id`.
- If hit: `status=rejected`, `error=duplicate_of:<trial_id>`, `reset_hard(parent)`, **no commit**.
- If miss: proceed; on any terminal status except crash-before-fingerprint, store the row.

Reverted trials **do** occupy the fingerprint space (they are evidence). Crashes before a stable tree do not.

### 4.2 v2 (only if v1 false-positives on a real pilot)

Embed `hypothesis + unified diff` (hashing trick or a local sentence embedding). Reject if cosine > τ to a prior trial. SemHash is an implementation option, not an ADR. Still no Git rewrite.

### 4.3 Code touch list

| Path | Change |
|------|--------|
| `storage/db.py` | Table `trial_fingerprints(loop_id, control_document_id, fingerprint, trial_id, created_at)`. |
| `loops/service.py` | Compute + check + insert around the existing porcelain/diff guards. |
| `agents/simple_loop_agent.py` | Stop appending `# agent touch N` as a uniqueness hack. |
| `tests/acceptance/test_phase6_dedup.py` | Same hparams twice → second `rejected` with `duplicate_of`; first still in Git if it committed. |

### 4.4 Exit criteria (Wave B)

- [ ] Duplicate hparam proposal does not create a hub commit.
- [ ] Distinct structural edits with the same hparams still run (structural hash differs).
- [ ] INV-08: earlier trial objects remain fetchable.

**Do not build in Wave B:** compaction that deletes commits; collapsing KG nodes; LLM “is this the same idea?”.

---

## 5. Wave C — Leaf search, no LLM (C1 + C3)

**Goal:** The DAG becomes the experiment tree the Master Plan already described. Keep remains vs. **global** best (INV-02). Surprise is a **proposer** signal, not a keep signal.

### 5.1 API / loop change

`propose_trial(..., parent_commit: str | None = None)`:

- Default: today's `loop.best_commit`.
- If set: must resolve in the workspace Git (or hub). `reset_hard(parent_commit)`. `trial.parent_commit = that hash`.
- Keep comparison baseline is still `loop.best_metric` / `loop.best_commit` as incumbent for Wave A pairing.
- After the trial, **always** `dag.push` when a `commit_hash` exists, with `status` in `{kept, reverted, evidence}`. Reverts stay on the hub as leaves of their parent.

This is the missing AgentHub mechanic. Without it, C1 is impossible.

### 5.2 Heuristic experiment manager

Replace (or sit beside) `SimpleLoopAgent._propose_edit`:

1. `leaves = dag.leaves()`. If empty, behave as today.
2. Score each leaf:
   - `unexplored_neighbors`: unused hparam steps adjacent to that leaf's parsed hparams.
   - `surprise`: absolute residual of last metric vs. the running mean of its siblings (high = interesting).
   - `failures`: consecutive revert streak on that lineage (low = exhausted).
3. Pick `argmax(unexplored + surprise - exhaustion)`.
4. Propose a **single-axis** step from that leaf (one variable per trial — closer to a real lab notebook than the current 4-axis scramble).
5. Board post when a leaf is marked exhausted (`3` consecutive reverts on that lineage) or surprising (metric jump > 2σ of siblings).

No model calls. No `program.md` rewrite as a keep path.

### 5.3 Code touch list

| Path | Change |
|------|--------|
| `loops/service.py` | Honor `parent_commit`; incumbent for pairing stays `best_commit`. |
| `api/server.py` + CLI | Pass through optional parent. |
| `agents/simple_loop_agent.py` or `agents/leaf_search_agent.py` | Leaf scoring + single-axis edits + always-push. |
| `tests/acceptance/test_phase6_leaf_search.py` | Two children of the same parent exist as hub leaves; a keep from a non-best parent still has to beat **global** best; exhausted leaf posts to the board. |
| `tests/acceptance/test_section8_dag.py` | Still green (three concurrent agents). |

### 5.4 Exit criteria (Wave C)

- [ ] `leaves` can return >1 node after a mixed keep/revert run.
- [ ] A trial parented at a non-best leaf that fails to beat global best is `reverted` (or evidence) and still fetchable.
- [ ] Board contains an exhaustion or surprise post on a 6+ trial run.
- [ ] No LLM dependency in `pyproject.toml` for this wave.

**Do not build in Wave C:** manuscript generation, self-review, MCTS with an LLM critic, keep-on-surprise.

---

## 6. Deferred (do not start)

| Item | Why not now |
|------|-------------|
| C13 community summaries in the context pack | Needs Wave C leaves to summarize. Template clustering on hparam fingerprints is a half-day follow-up, not a wave. |
| C12 GraphFlow | Empty graph. Revisit only if KG writes are authorized by a later ADR. |
| C9 anytime-valid certificates as a full SEA harness | Wave A certificate is the subset we need. |
| LLM experiment manager (C1 full) | After Wave A is hostile under an LLM-editable `train.py`, and after sandbox P3 if the model can shell out. |
| KG writes / skill promotion (W2–W6) | Bibliography §6. Contribution from hostile metrics only; not this slice. |
| gVisor / cgroups / OIDC | ADR-005 non-goals until the pilot demands them. |

---

## 7. Sequence and ownership

```text
Week 1     Wave A contracts + paired eval harness + redaction + adversarial tests
Week 1–2   Wave A e-process (or majority fallback) + runbook
Week 2     Wave B fingerprints + drop comment-bump hack
Week 2–3   Wave C parent_commit + always-push + leaf scorer
(later)    C13 briefing → only then consider LLM proposer or GraphFlow
```

One owner per wave. Wave B may overlap Wave A tests but must not merge before A's contract bump. Wave C **must not** merge before A: a tree search against a single-shot keep multiplies false keeps.

Pilot metrics to log (Master Plan §11), now with meaning:

| Metric | Wave that makes it honest |
|--------|---------------------------|
| Keep rate | A (false keeps fall) |
| Crash rate | unchanged |
| Budget exhaustion | A early-stop + B skipped dupes |
| Recovery success | unchanged |
| Leaves / kept | C (should rise above 1) |
| Duplicate-reject rate | B |

---

## 8. Non-goals (repeat so they stay dead)

- Do not relax sandbox, last-match parse, or `metric_override` rejection.
- Do not let `program.md` or the agent set `keep_gate.seeds`.
- Do not rewrite Git history to compact or dedup.
- Do not compare keep to the trial parent’s metric.
- Do not turn on graph writes to “use” C12.
- Do not cite D1–D5 compilations in new ADRs.

---

**End of plan.** Implement Wave A first. If only one patch lands this cycle, it is the sealed keep certificate.
