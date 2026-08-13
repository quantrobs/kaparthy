# Phase 6 Technical Plan — Work Packages 1–6

**Status:** Authoritative for Phase 6 engineering  
**Date:** 2026-08-12  
**Authority:** IT Architect  
**ADR:** [ADR-006](adr/ADR-006-phase6-top-slice.md)  
**Literature:** [bibliography.md](bibliography.md)

Six work packages, in bibliography order. INV-01–12 do not change. WP1 bumps contracts to additive `v0.1.2`. WP4–5 add optional response fields only. WP6 is tests and process.

| WP | Bibliography | Build now? | Gate |
|----|--------------|------------|------|
| **1** | C6 PACE + C7 sealed holdout | **Yes** | — |
| **2** | C4 SemDeDup | **Yes** | After WP1 contracts land (may overlap tests) |
| **3** | C1 / C3 leaf search + surprise | **Yes** | After WP1. A tree against single-shot keep multiplies false keeps. |
| **4** | C13 GraphRAG community summaries | Planned | After WP3 produces >1 leaf |
| **5** | C12 GraphFlow retrieval | Planned | After WP1 + a **system** lineage projector. Agent KG writes stay **off**. |
| **6** | C8 standing release gates | **Yes — start day 1** | None. Tests first. Every later WP merges through this suite. |

If only one patch lands: **WP1**. If only tests land first: **WP6**.

---

## 0. What the code does today

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

DagService.build_context_pack
  essentials + lineage[:8] + board[:5]
  chars/4 budget; no cluster briefing

GraphService.subgraph
  BFS hops + prefer-verified + chars/4
  Agent path: graph writes off → walk is empty
```

| Hole | File | WP that closes it |
|------|------|-------------------|
| Single-shot keep | `loops/service.py` `_run_and_parse_metric` | 1 |
| `SEED` is mutable | demo `train.py` | 1 |
| Sealed values would leak | `dag/service.py` `build_context_pack` | 1 |
| Near-duplicate commits | `simple_loop_agent.py` `# agent touch N` | 2 |
| No parent choice / evidence not pushed | `propose_trial`, simple agent | 3 |
| Context pack is a dump, not a briefing | `build_context_pack` | 4 |
| Subgraph is hop-count, graph is empty on agent path | `graph/service.py` | 5 |
| New capability can merge on README promises | no standing suite name | 6 |

---

## 1. WP1 — Sealed paired keep-gate (C6 + C7)

**Goal:** A `kept` trial is a **certificate** over a sealed instance set the agent cannot see or author. Default remains `single_shot` so §8 stays green.

### 1.1 Keep-gate

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
| `mode` | `single_shot` (default) or `paired_pace`. |
| `seeds` | **Sealed.** Never rendered into `program.md`, context pack, board posts, or trial `hypothesis`. |
| Eval injection | Harness sets `AGENTIC_EVAL_SEED` at run time. Do not commit seed rewrites. Agent-written `SEED = …` is ignored under `paired_pace`. |
| Paired instances | For each seed: run **incumbent** (`best_commit`) and **candidate** (trial commit) with the same injected seed; last-match parse both. |
| PACE e-process | Wealth `W=1`. Candidate wins the Control Document comparison → `W ← W(1+λ)`, else `W ← W(1-λ)`. |
| Keep | `W > 1/alpha` and ≥ `n_min` pairs. |
| Revert | `n_max` reached, **or** wealth cannot reach `1/alpha` even if all remaining pairs win (early stop). |
| Fallback | Majority-of-seeds + better mean. Ship only if e-process slips. Never ship single-shot labeled as `paired_pace`. |

Demo `train.py` reads `os.environ.get("AGENTIC_EVAL_SEED", SEED)`.

### 1.2 Contract (`v0.1.2`, additive)

`additionalProperties: false` stays. Old documents remain valid.

| Schema | New optional fields |
|--------|---------------------|
| `control-document` | `keep_gate`: `mode`, `n_min`, `n_max`, `alpha`, `lambda`, `seeds`, `seed_env` |
| `trial` | `keep_certificate`: `mode`, `n_pairs`, `wins`, `losses`, `e_value`, `alpha`, `mean_incumbent`, `mean_candidate`, `early_stopped` |
| `evaluation-result` | `e_value`, `n_instances`, `sealed`, `pair_summary` (no raw seeds) |

OpenAPI `0.1.2`. No new required endpoints. `ControlService.render_program` strips `keep_gate.seeds`.

### 1.3 Code touch list

| Path | Change |
|------|--------|
| `contracts/v0.1.2/` | Copy v0.1.0; add optional fields. Point `core/validation.py` at 0.1.2. |
| `models/schemas.py` | `KeepGate`, `KeepCertificate`. |
| `loops/service.py` | `_evaluate_paired(ctl, incumbent_hash, candidate_hash)` → certificate; keep/revert from it when `paired_pace`. |
| `eval/service.py` | Persist certificate as `EvaluationResult` (`sealed=true`, no seeds in `notes`). |
| `dag/service.py` | Redact `keep_gate.seeds` from context pack. Protected paths stay first. |
| `control/service.py` | Redact seeds from `program.md`. |
| `examples/demo_workspace/train.py` | Honor `AGENTIC_EVAL_SEED`. |
| `invariants/checks.py` | `require_sealed_keep(certificate)` — keep forbidden if not sealed under `paired_pace`. |
| `tests/acceptance/test_phase6_keep_gate.py` | WP1 gate. |

### 1.4 Exit criteria

- [ ] `v0.1.2` published; v0.1.0 fixtures still validate.
- [ ] Default `single_shot` keeps §8 + Phase 4.5 + Phase 5 green.
- [ ] `paired_pace` keep requires sealed pairs; seeds absent from every agent-visible surface.
- [ ] Lucky-single-seed candidate is `reverted` and still writes a certificate.
- [ ] Runbook: how to declare `keep_gate` on a pilot control document.

**Out of WP1:** LLM judge, self-review, changing `comparison.function`, cgroups.

---

## 2. WP2 — Frontier filter (C4)

**Goal:** Near-duplicate proposals die **before** Git commit. History stays append-only (INV-08).

### 2.1 v1 fingerprint (no embeddings)

1. Parse `NAME = value` for `LR`, `STEPS`, `HIDDEN`, `L2`.
2. Strip comments and those lines; SHA-256 the remainder.
3. Fingerprint = `hparams_tuple || structural_hash`.

Before `git.commit` in `propose_trial`:

- Lookup in `trial_fingerprints` for this `control_document_id`.
- Hit → `status=rejected`, `error=duplicate_of:<trial_id>`, `reset_hard(parent)`, **no commit**.
- Miss → proceed; store the row on any terminal status except crash-before-tree.

Reverted trials occupy fingerprint space (they are evidence).

### 2.2 v2 (only if v1 false-positives on a real pilot)

Embed `hypothesis + unified diff`. Reject if cosine > τ. SemHash is an implementation option, not an ADR. Still no Git rewrite.

### 2.3 Code touch list

| Path | Change |
|------|--------|
| `storage/db.py` | `trial_fingerprints(loop_id, control_document_id, fingerprint, trial_id, created_at)`. |
| `loops/service.py` | Compute + check + insert around the porcelain/diff guards. |
| `agents/simple_loop_agent.py` | Stop `# agent touch N` uniqueness hack. |
| `tests/acceptance/test_phase6_dedup.py` | Same hparams twice → second `rejected` with `duplicate_of`. |

### 2.4 Exit criteria

- [ ] Duplicate hparam proposal does not create a hub commit.
- [ ] Distinct structural edits with the same hparams still run.
- [ ] INV-08: earlier trial objects remain fetchable.

**Out of WP2:** compaction that deletes commits; LLM “is this the same idea?”.

---

## 3. WP3 — Leaf search, no LLM (C1 + C3)

**Goal:** The DAG becomes the experiment tree the Master Plan already described. Keep remains vs. **global** best (INV-02). Surprise is a **proposer** signal, not a keep signal.

### 3.1 Loop / API

`propose_trial(..., parent_commit: str | None = None)`:

- Default: `loop.best_commit`.
- If set: must resolve in workspace Git (or hub). `reset_hard(parent_commit)`. `trial.parent_commit = that hash`.
- Keep baseline is still `loop.best_metric` / `loop.best_commit` as WP1 incumbent.
- After the trial, **always** `dag.push` when a `commit_hash` exists, status in `{kept, reverted, evidence}`.

Without always-push, WP3 cannot create leaves and WP4 has nothing to cluster.

### 3.2 Heuristic experiment manager

Replace (or sit beside) `SimpleLoopAgent._propose_edit`:

1. `leaves = dag.leaves()`. If empty, behave as today.
2. Score each leaf:
   - `unexplored_neighbors` — unused hparam steps adjacent to that leaf.
   - `surprise` — residual vs. sibling mean (high = interesting).
   - `failures` — consecutive revert streak (high = exhausted).
3. Pick `argmax(unexplored + surprise − exhaustion)`.
4. Propose a **single-axis** step from that leaf.
5. Board post when a leaf is exhausted (3 consecutive lineage reverts) or surprising (jump > 2σ of siblings).

No model calls. No `program.md` rewrite as a keep path.

### 3.3 Code touch list

| Path | Change |
|------|--------|
| `loops/service.py` | Honor `parent_commit`; incumbent for pairing stays `best_commit`. |
| `api/server.py` + CLI | Pass through optional parent. |
| `agents/leaf_search_agent.py` (or upgrade simple agent) | Leaf scoring + single-axis edits + always-push. |
| `tests/acceptance/test_phase6_leaf_search.py` | Two children of one parent are hub leaves; keep from a non-best parent must still beat **global** best; exhausted leaf posts to the board. |

### 3.4 Exit criteria

- [ ] `leaves` can return >1 node after a mixed keep/revert run.
- [ ] A trial parented at a non-best leaf that fails global best is `reverted`/`evidence` and fetchable.
- [ ] Board contains an exhaustion or surprise post on a 6+ trial run.
- [ ] No LLM dependency in `pyproject.toml`.

**Out of WP3:** manuscript generation, self-review, MCTS-with-LLM, keep-on-surprise.

---

## 4. WP4 — Leaf community summaries (C13)

**Goal:** The context pack becomes a **briefing** of the frontier, not a dump of the last eight lineage lines. Steal GraphRAG’s *local → community → query-focused summary* pattern. Do **not** steal unconstrained LLM graph writes. Summaries are derived artifacts, never Claims.

### 4.1 Why this is not GraphFlow

WP4 reads the **commit DAG + fingerprints** (WP2/WP3). It does not require KG writes. WP5 walks a typed graph. Shipping WP4 first gives agents a usable briefing the night WP3 creates multiple leaves.

### 4.2 Algorithm (v1, no LLM)

After each `dag.push`, or lazily inside `build_context_pack`:

1. Take current `leaves()` (cap 64).
2. Cluster by WP2 hparam fingerprint **prefix** (the tuple, ignoring structural hash). Same `(LR bucket, STEPS bucket, HIDDEN, L2)` → same community.
   - Continuous axes bucketed: `LR` by log10 decade, `STEPS` by `{≤20, 21–60, 61–120, >120}`.
3. For each community with ≥1 leaf, emit a fixed template:

```text
CLUSTER lr~0.1 steps~40–60 n=3
  best=0.0124 @ abcdef1 kept=2 reverted=1
  last: "single-axis STEPS 40→60" status=reverted
  surprise=0.8 exhausted=false
```

4. Sort communities: lowest/highest best-metric (per `direction`), then surprise desc.
5. Insert a `BRIEFING` section in `build_context_pack` **after** essentials (protected paths, metric, best) and **before** raw `LINEAGE`. Drop whole clusters when the chars/4 budget is hit. Never drop essentials or the redaction of `keep_gate.seeds`.
6. Persist the briefing as an **Artifact** (content-addressed blob) with provenance `{algorithm: "leaf-community-v1", leaf_hashes: [...], created_from_run}`. Optional `DERIVED_FROM` edges only if WP5’s projector exists; WP4 must work with the blob + context-pack section alone.

### 4.3 v2 (optional, later)

LLM rewrite of the same template into two sentences, stored as a second Artifact tagged `derived_summary`. Still not a Claim. Still budgeted. Still must cite `leaf_hashes`. Skip until a pilot shows the template is unreadable.

### 4.4 Contract

No required schema bump. Additive optional fields on the context-pack response (OpenAPI already loose):

```json
{
  "briefing": [
    {
      "cluster_id": "lr0.1_s40",
      "n": 3,
      "best_metric": 0.0124,
      "best_hash": "abcdef1",
      "kept": 2,
      "reverted": 1,
      "exhausted": false,
      "text": "CLUSTER ..."
    }
  ],
  "briefing_artifact_uri": "artifacts/sha256/..."
}
```

`token_accounting` remains `approx_chars_div_4`. `truncated` is true if any cluster was dropped.

### 4.5 Code touch list

| Path | Change |
|------|--------|
| `dag/communities.py` (new) | Cluster leaves; render template; no I/O except reading annotations. |
| `dag/service.py` `build_context_pack` | Insert `BRIEFING` section; return `briefing` + uri. |
| `storage/artifacts.py` | `put_derived(kind="leaf_briefing", payload, provenance)`. |
| `tests/acceptance/test_phase6_briefing.py` | Two hparam neighborhoods → two clusters; tight budget keeps essentials + ≥1 cluster and sets `truncated`; seeds still absent. |

### 4.6 Exit criteria

- [ ] A 10-trial leaf-search run produces ≥2 clusters in the pack when hparams actually split.
- [ ] Briefing is system-authored (artifact provenance names `leaf-community-v1`, not an agent_id).
- [ ] INV-12: `approx_tokens_used` still honors the budget.
- [ ] C7: sealed seeds still redacted.

**Out of WP4:** treating summaries as Claims; writing them through `POST /graph/updates` from the agent; dropping the token budget; GraphRAG Leiden over the full KG (that is WP5’s problem).

---

## 5. WP5 — GraphFlow retrieval (C12)

**Goal:** Replace hop-count BFS with a capacity-constrained, diversity-aware walk so the pack is **relevant**, not merely nearby. INV-12 still holds. Agent `--enable-graph-writes` stays **off**.

### 5.1 Prerequisite the paper does not mention

`subgraph()` is empty on the agent path because nothing writes nodes. GraphFlow over an empty graph is a no-op. WP5 therefore has two parts:

1. **System lineage projector** (not agent writes).
2. **Flow retriever** that `subgraph()` calls.

### 5.2 System lineage projector

A loop/DAG hook, run after every terminal trial that has a `commit_hash`. Authored by `agent_id="system-projector"`. Reversible (INV-09 style: projector writes are versioned; a later projector version supersedes via `SUPERSEDES`, old nodes stay addressable).

| Node | id | Properties (no secrets) |
|------|-----|-------------------------|
| `Commit` | `commit:<hash>` | hash, status, agent_id, hypothesis (truncated), parent hashes |
| `Metric` | `metric:<hash>:<name>` | name, value, direction |
| `Evaluation` | `eval:<trial_id>` | decision, `sealed`, `e_value` / wins — **never seeds** |
| `Artifact` | briefing uri from WP4 | `kind=leaf_briefing` |

| Edge | From → To |
|------|-----------|
| `PARENT_OF` | parent Commit → child Commit (Git topology; Git still wins) |
| `HAS_METRIC` | Commit → Metric |
| `EVALUATED_BY` | Commit → Evaluation |
| `DERIVED_FROM` | Briefing Artifact → member Commit hashes |
| `PRODUCED` | AgentRun (if present) → Commit |

**Forbidden in the projector:** `Claim` nodes. Claims remain human- or later-authorized writes. This is how WP5 does not become a skill library (bibliography §6).

Idempotent: `INSERT OR REPLACE` on stable ids. Projector must be callable as `ah graph-project --loop <id>` to rebuild after a crash.

### 5.3 Flow retriever

Replace the BFS body of `GraphService.subgraph` with a ranked walk. Keep the same function signature so `/graph/subgraph` stays stable.

```text
subgraph(seed_ids, hops, token_budget, prefer_verified, query=None)
  1. Resolve seeds (default: current leaf Commit + its Metric + Evaluation).
  2. Candidate expansion: same adjacency as today, capped at hops.
  3. Edge weight:
       PARENT_OF / EVALUATED_BY / HAS_METRIC = 1.0
       DERIVED_FROM / ABOUT                 = 0.6
       SUPPORTS (only if a Claim ever exists) = 0.8 if provenance has source_ids else 0.2
       CONTRADICTS                          = 0.7 (keep — disagreement is signal)
  4. Node prior:
       prefer_verified Claims still rank above is_inference
       Evaluation.sealed=true ranks above missing certificate
       Metric closer to best_metric ranks above worse siblings
  5. Diversity: MMR. After picking node u, penalize nodes with the same
     WP2 hparam cluster as u (λ ≈ 0.4). Three near-duplicate keept trials
     cannot fill the pack.
  6. Serialize under chars/4. Always include seeds. Set truncated.
```

`query` is optional free text (objective, or the agent’s next hypothesis). v1 may ignore `query` and use seed + metric proximity. v2: token overlap of `query` against `hypothesis` / cluster briefing text.

Do **not** add process-level RL on the retriever (C12’s training trick). This is a deterministic ranker.

### 5.4 Wiring into the context pack

`build_context_pack` after WP4:

```text
essentials (redacted control, protected paths, best)
BRIEFING (WP4 clusters)
GRAPH   (WP5 triples, only if projector has written ≥1 Commit)
LINEAGE (fallback; shrink first when budget is tight)
BOARD
```

If the projector has not run, GRAPH is omitted and behavior equals WP4. INV-12: combined sections still use one char budget.

### 5.5 Contract

Additive, optional:

- `POST /graph/subgraph` body may include `query: string`.
- Response may include `ranker: "graphflow-v1"`, `diversity: "mmr_hparam_cluster"`.
- `POST /graph/project` (system/admin key only) `{loop_id}` → `{writes, commits_projected}`.

Agent keys cannot call `/graph/project`. `AGENTIC_REQUIRE_AUTH=1` in pilot.

### 5.6 Code touch list

| Path | Change |
|------|--------|
| `graph/projector.py` (new) | Trial/DAG → Commit/Metric/Evaluation/edges. No Claims. |
| `graph/flow.py` (new) | Weighted expansion + MMR. Pure function over nodes/edges. |
| `graph/service.py` `subgraph` | Delegate to `flow.retrieve`; keep budget/seed guarantees. |
| `loops/service.py` | After ledger write, `projector.project_trial(trial)` (best-effort; failure must not fail the trial). |
| `api/server.py` | `POST /graph/project` admin-only. |
| `dag/service.py` | Optional GRAPH section in the pack. |
| `tests/acceptance/test_phase6_graphflow.py` | Projector after 6 trials creates Commit+Metric+EVALUATED_BY; subgraph with tiny budget returns diverse clusters not 3 clones of the best leaf; seeds never appear on Evaluation nodes; agent key cannot project. |

### 5.7 Exit criteria

- [ ] A WP3 run of 8+ trials leaves a typed lineage graph **without** `--enable-graph-writes`.
- [ ] `subgraph` token budget still holds; `truncated` is honest.
- [ ] Diversity: pack from a 3-duplicate-best neighborhood includes ≥1 node from another cluster when one exists.
- [ ] No Claim node exists unless a human/admin wrote it.
- [ ] INV-05/06/07/12 still pass `tests/acceptance/test_section8_graph.py`.

**Out of WP5:** agent Claims; turning default graph writes on; process-reward training of the walk; replacing Git topology with RAG chunks; billing from `chars/4`.

---

## 6. WP6 — Standing release gates (C8)

**Goal:** Every new capability ships only if a **pre-declared** suite passes **and** standing invariants still hold. README promises are not a gate. This work package starts first (it is tests + a named suite) and stays red-or-green for WP1–5 merges.

### 6.1 Standing suite

Marker: `@pytest.mark.release_gate`. CI job `release-gates` in `.github/workflows/ci.yml` (in addition to the existing full suite). A WP merge that makes this job red does not ship.

| Gate id | Test | Already exists? | Protects |
|---------|------|-----------------|----------|
| G-INV-01 | `test_protected_path_rejected_before_commit` | Yes | Eval surface |
| G-INV-01b | `test_mutable_allowlist_rejects_extra_files` | Yes | Allowlist |
| G-INV-02 | `test_metric_override_cannot_keep` | Yes | Hostile keep |
| G-INV-02b | `test_fake_print_uses_last_match` | **Add** | Last-match parse |
| G-INV-03 | crash mid-training reverts + runnable | Yes | Revert |
| G-INV-04 | ledger entry on keep and revert | covered by loop tests | Append-only |
| G-SEED | `test_seed_not_in_context_or_program` | **Add (WP1)** | C7 |
| G-PACE | `test_lucky_single_seed_does_not_keep` | **Add (WP1)** | C6 |
| G-CERT | `test_keep_writes_certificate` | **Add (WP1)** | C9 subset |
| G-HOLD | `test_agent_cannot_author_holdout` | **Add (WP1)** | C7 |
| G-DUP | `test_duplicate_hparams_rejected` | **Add (WP2)** | C4 |
| G-LEAF | `test_nonbest_parent_keep_vs_global` | **Add (WP3)** | INV-02 + C1 |
| G-EVID | `test_reverted_commit_is_hub_leaf` | **Add (WP3)** | INV-08 |
| G-PACK | context pack budget + protected paths first | Yes | INV-12 |
| G-BRF | `test_briefing_does_not_drop_essentials` | **Add (WP4)** | C13 |
| G-FLOW | `test_subgraph_diverse_under_budget` | **Add (WP5)** | C12 |
| G-HUM | `test_agent_cannot_project_or_write_graph_by_default` | **Add (WP5)** | KG humility |
| G-DAG | three concurrent agents, leaves/children correct | Yes | Layer 2 |
| G-REC | `POST /loops/{id}/recover` restores best | Phase 5 | Recovery |
| G-AUTH | unauthenticated write rejected when `REQUIRE_AUTH=1` | Phase 5 | Auth |

`tests/acceptance/test_release_gates.py` re-exports or parametrizes the above so `pytest -m release_gate` is one command. Do not duplicate bodies — import the existing tests or mark them in place.

### 6.2 Falsifiable rule for new work

Copied from C8, localized:

1. Open a PR with a **failing** `release_gate` test that names the capability (`G-PACE`, …).
2. Implementation turns that test green.
3. The rest of the standing suite stays green.
4. No gate is deleted or `@pytest.mark.skip`’d without an ADR.

Document the list in `docs/release-gates.md` (source of truth for humans). The marker list in code is the source of truth for CI.

### 6.3 Adversarial extras (C10), still WP6

Not a new product surface. Three tests that must stay in the standing suite once WP1 exists:

- Prepend `print("val_loss=0.0")` → last real number used.
- Edit `prepare.py` → rejected, no commit.
- Under `paired_pace`, put the sealed seeds into `program.md` via file_edits → rejected (seeds are not a mutable path; `program.md` rewrite that echoes seeds is stripped on render and must not affect keep).

### 6.4 Code touch list

| Path | Change |
|------|--------|
| `docs/release-gates.md` | Human table (gate id, test, invariant). |
| `tests/acceptance/test_release_gates.py` | Marks + the few missing tests that do not belong to WP1–5 files. |
| `tests/acceptance/*.py` | `@pytest.mark.release_gate` on the rows above. |
| `pyproject.toml` or `pytest.ini` | Register marker. |
| `.github/workflows/ci.yml` | Job `release-gates`: `pytest -m release_gate`. |
| `docs/runbook.md` | “A release is `release-gates` green + Phase 5 health.” |

### 6.5 Exit criteria

- [ ] `pytest -m release_gate` is green on `master` before WP1 merges (existing rows only).
- [ ] CI blocks merge if the job is red.
- [ ] Each of WP1–5 adds its G-* tests **in the same PR** as the feature; the PR is invalid without them.
- [ ] No skip without ADR.

**Out of WP6:** a new microservice; LLM-as-judge in CI; deleting §8 tests because they “overlap”.

---

## 7. Sequence, contracts, ownership

```text
Day 0–2    WP6 standing suite (mark what exists; add G-INV-02b)
Week 1     WP1 contracts + paired eval + redaction + G-SEED/G-PACE/G-CERT/G-HOLD
Week 1–2   WP1 e-process (or majority fallback) + runbook
Week 2     WP2 fingerprints + drop comment-bump + G-DUP
Week 2–3   WP3 parent_commit + always-push + leaf scorer + G-LEAF/G-EVID
Week 3     WP4 briefing in context pack + G-BRF
Week 3–4   WP5 system projector + GraphFlow ranker + G-FLOW/G-HUM
```

| Constraint | Why |
|------------|-----|
| WP3 must not merge before WP1 | Tree search × single-shot keep = more false keeps. |
| WP4 must not merge before WP3 | One leaf is not a community. |
| WP5 must not merge before WP1 | Projector would persist unsealed “evaluations” as if they were certificates. |
| WP5 must not enable agent graph writes | Bibliography §6. |
| WP2 may overlap WP1 tests | Fingerprints do not depend on pairing. |
| WP6 never waits | It is the merge valve. |

Pilot metrics (Master Plan §11), now with owners:

| Metric | Honest after |
|--------|----------------|
| Keep rate | WP1 |
| Crash rate | already |
| Budget exhaustion | WP1 early-stop + WP2 skipped dupes |
| Recovery success | already |
| Leaves / kept | WP3 |
| Duplicate-reject rate | WP2 |
| Pack truncated rate / clusters shown | WP4 |
| Subgraph diversity (≥2 clusters when present) | WP5 |

---

## 8. Non-goals (all six packages)

- Do not relax sandbox, last-match parse, or `metric_override` rejection.
- Do not let `program.md` or the agent set `keep_gate.seeds`.
- Do not rewrite Git history to compact or dedup.
- Do not compare keep to the trial parent’s metric.
- Do not turn on agent graph writes to “use” WP5.
- Do not promote briefing text or flow-selected nodes to Claims.
- Do not cite D1–D5 compilations in new ADRs.
- Do not add an LLM until WP1 is green under an LLM-editable `train.py`.

---

**End of plan.** Implement in order 6 → 1 → 2 → 3 → 4 → 5. The only legal skip is “WP4 template-only, skip v2 LLM rewrite.”
