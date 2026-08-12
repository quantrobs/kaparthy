# Bibliography

**Document status:** Collected literature for the Agentic Research Platform  
**Date:** 2026-08-12  
**Authority:** IT Architect  
**Companion to:** `MASTER-PLAN.md` §2 / §12

This file is the annotated collection of sources that already ground Kaparthy, plus papers gathered to improve the four-layer architecture in Phase 6. It is **not** a contract and does not change invariants. Implementation still requires an ADR + schema version bump.

Kaparthy stays the hostile experiment OS (measured loop, Git DAG, sealed eval, humble KG). Skill-library compounding belongs in sibling work, not here.

## How to read this file

| Tag | Meaning |
|-----|---------|
| **F** | Foundational — already synthesized into the Master Plan / ADRs |
| **C** | Candidate — collected for Phase 6; not yet design-shaping |
| **W** | Warning — useful negative result; do not implement naively |
| **D** | Declined — reviewed and not to be cited as architecture authority |

Verification is honest: titles, venues, and abstracts were checked. Not every PDF was line-read. Treat **C** entries as next reading, not as approved design.

---

## 1. Foundational sources (already in the architecture)

These are the sources Master Plan §2 already synthesizes. Keep citing the primaries, not viral compilations.

| ID | Work | Link | Role in Kaparthy |
|----|------|------|------------------|
| F1 | Karpathy, *autoresearch* (GitHub, Mar 2026) | [github.com/karpathy/autoresearch](https://github.com/karpathy/autoresearch) | Layer 1 measured loop: `program.md` + mutable `train.py` + protected eval surface + keep/revert |
| F2 | Karpathy, AgentHub sketch + public forks | — | Layer 2: commit DAG as experiment lineage; leaves are the frontier; message board |
| F3 | Karpathy, Sequoia AI Ascent 2026 summary (30 Apr 2026) | [karpathy.bearblog.dev/sequoia-ascent-2026](https://karpathy.bearblog.dev/sequoia-ascent-2026/) | Software 3.0, agentic engineering, jagged intelligence |
| F4 | Karpathy, “Verifiability” (17 Nov 2025) | [karpathy.bearblog.dev/verifiability](https://karpathy.bearblog.dev/verifiability/) | Hostile metrics: if it is not resettable, efficient, and rewardable, do not keep it |
| F5 | Karpathy, “Animals vs Ghosts” (1 Oct 2025) | [karpathy.bearblog.dev/animals-vs-ghosts](https://karpathy.bearblog.dev/animals-vs-ghosts/) | LLMs are ghosts, not animals; control/eval/memory live outside the context window |
| F6 | Karpathy, “2025 LLM Year in Review” (Dec 2025) | [karpathy.bearblog.dev/year-in-review-2025](https://karpathy.bearblog.dev/year-in-review-2025/) | RLVR + jagged intelligence; why a ratchet beats vibe |
| F7 | Anthropic, *Building Effective Agents* (2024) | [anthropic.com/engineering/building-effective-agents](https://www.anthropic.com/engineering/building-effective-agents) | Workflows before swarms; measured loop before multi-agent |
| F8 | Anthropic, Dynamic Workflows (2026) + Knowledge Graph Construction Cookbook | — | Layer 4 overlay; typed state; KG as complementary to the DAG |
| F9 | Independent “Graph Engineering” technical note (Jul 2026) | in-repo: `Karpathy-Graph-Engineering-Systems.pdf` | Mapping F1–F8 onto four layers; **not** affiliated with Karpathy or Anthropic |
| F10 | Frozen contracts `v0.1.0-frozen` | `contracts/v0.1.0/` | Authoritative schemas; bibliography cannot override these |

In-repo ADRs that encode the above: ADR-001 storage, ADR-003 Git-authoritative DAG, ADR-004 hostile keep, ADR-005 hardening.

---

## 2. Layer 1 — Measured loop: what to try next

Current gap: `SimpleLoopAgent` is a 4-axis grid (`LR` / `STEPS` / `HIDDEN` / `L2`). The ratchet is honest; the proposer is dumb.

| ID | Work | Citation | Steal | Do not steal |
|----|------|----------|-------|--------------|
| C1 | *The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search* | Yamada et al., 2025. [arXiv:2504.08066](https://arxiv.org/abs/2504.08066). Code: [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) | Progressive tree search under an experiment-manager; propose children of **leaves**, not of a single best commit | Manuscript generation, self-review as keep signal, relaxing protected files |
| C2 | *The AI Scientist: Towards Fully Automated AI Research* | Lu et al., *Nature* (2026). [doi:10.1038/s41586-026-10265-5](https://www.nature.com/articles/s41586-026-10265-5). Preprint lineage: [arXiv:2408.06292](https://arxiv.org/abs/2408.06292) | End-to-end research lifecycle as a pipeline of verifiable steps | Treating peer-review theater as scientific validity |
| W1 | *Evaluating Sakana's AI Scientist* | SIGIR Forum, Oct 2025. [doi:10.1145/3769733.3769747](https://dl.acm.org/doi/10.1145/3769733.3769747) | Why last-match parse and Git-as-truth stay: 42% experiment failure, hallucinated numbers, ~8% code delta | Using this as a reason to abandon autonomous loops |
| C3 | *AutoDiscovery: Open-ended Scientific Discovery via Bayesian Surprise* | Agarwal et al., NeurIPS 2025. [arXiv:2507.00310](https://arxiv.org/abs/2507.00310) | Score candidate edits by Bayesian surprise / information gain once the grid is exhausted; publish “leaf exhausted / leaf surprising” on the board | Replacing the declared Control Document metric with surprise |

**Phase-6 implication:** keep the hostile loop. Replace only `_propose_edit`.

---

## 3. Layer 2 — Commit DAG: compaction and semantic dedup

Master Plan §4.2 already names the production holes: compaction, stronger auth, semantic deduplication. Failed experiments remain evidence (INV-08).

| ID | Work | Citation | Steal | Do not steal |
|----|------|----------|-------|--------------|
| C4 | *SemDeDup: Data-efficient learning at web-scale through semantic deduplication* | Abbas et al., 2023. [arXiv:2303.09540](https://arxiv.org/abs/2303.09540) | Embed hypothesis + diff (+ metric trajectory); skip or mark `duplicate_of` **before** `propose_trial` | Rewriting Git history or dropping reverted commits |
| C5 | SemHash (software) | van Dongen & Tulkens, 2025. [github.com/MinishLab/semhash](https://github.com/MinishLab/semhash) | Lightweight implementation path for C4 | Treating a library choice as an ADR |

Dedup is a **frontier filter**, not a history rewrite. Git remains topology truth (ADR-003).

---

## 4. Layer 3 — Software 3.0: keep-gates and sealed evaluation

Current gap: `EvalService.evaluate_metric` is one scalar vs. last best. That is uncontrolled adaptive testing. `metric_override` is banned; last-regex parse stops fake prints. Neither stops an agent that trains on the val set or authors its own verifier.

| ID | Work | Citation | Steal | Do not steal |
|----|------|----------|-------|--------------|
| C6 | *PACE: Anytime-Valid Acceptance Tests for Self-Evolving Agents* | Shawn, 2026. [arXiv:2606.08106](https://arxiv.org/abs/2606.08106) | Paired anytime-valid commit gate (e-process); candidate vs. incumbent on identical instances; early-stop waste | Letting the agent author the held-out set |
| C7 | *Self-Authored Verification Is Unreliable in Heuristic Self-Improving Agents* | Guo et al., 2026. [arXiv:2607.24300](https://arxiv.org/abs/2607.24300) | Sealed, agent-invisible evaluation surface; agent sees accept/reject only | Any keep that the proposer can inspect and optimize |
| C8 | *Falsifiable Release Gates for Self-Improving Systems* | Soni, 2026. [arXiv:2607.13070](https://arxiv.org/abs/2607.13070) | Every new capability ships only if a pre-declared suite passes **and** standing invariants still hold | README promises as safety |
| C9 | *Self-Evolving Agents with Anytime-Valid Certificates* | Sengupta, 2026. [arXiv:2607.00871](https://arxiv.org/abs/2607.00871) | Frozen base + versioned harness; keep writes an auditable certificate (run id, instances, e-value, budget) | Unbounded self-modification of the evaluator |
| C10 | *Sycophancy to Subterfuge: Investigating Reward-Tampering in Large Language Models* | Denison et al., 2024. [arXiv:2406.10162](https://arxiv.org/abs/2406.10162) | Standing adversarial gates: fake-metric prints, protected-path probes, reward-channel edits | Assuming last-match parse is sufficient once an LLM edits `train.py` |
| C11 | *Reward Hacking in the Era of Large Models* | 2026. [arXiv:2604.13602](https://arxiv.org/abs/2604.13602) | Three mitigations that already rhyme with us: verifiable rewards, budgeted optimization, evaluator–policy isolation | Evaluator–policy co-evolution that lets the agent update the rubric |

**Phase-6 implication:** wrap keep with PACE + a sealed holdout. Highest-ROI first patch.

---

## 5. Layer 4 — Knowledge-graph overlay and context pack

Current gap: `subgraph()` is BFS + prefer-verified + `chars/4`. INV-12 holds. Relevance does not. Graph writes stay **off** by default.

| ID | Work | Citation | Steal | Do not steal |
|----|------|----------|-------|--------------|
| C12 | *Can Knowledge-Graph-based RAG Really Retrieve What You Need?* (GraphFlow) | Yu, Liu, Gu, Torr, Zhou; NeurIPS 2025 Spotlight. [arXiv:2510.16582](https://arxiv.org/abs/2510.16582) | Flow-style walk over Claim/Source/Commit/Evaluation; diversity so three near-duplicate kept trials do not fill the pack | Process-level reward supervision on retrieval; dropping the token budget |
| C13 | *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* | Edge et al., Microsoft, 2024. [arXiv:2404.16130](https://arxiv.org/abs/2404.16130) | Community summaries of **leaves** (LR cluster vs. architecture cluster) as derived artifacts with provenance | Unconstrained LLM graph writes; treating summaries as Claims |
| C14 | *Knowledge Graph-Guided Retrieval Augmented Generation* (KG2RAG) | Zhu et al., NAACL 2025. [arXiv:2502.06864](https://arxiv.org/abs/2502.06864) | Fact-level relationships between packed chunks (`program.md` + last N trials + Claims) | Replacing Git lineage with chunk RAG |

Token accounting remains labeled. If a real tokenizer is added, keep `token_accounting` explicit; do not bill from `chars/4`.

---

## 6. Warnings if graph writes are turned on

These are **not** a license to grow a skill library inside Kaparthy. They are the reasons `--enable-graph-writes` stays off until C6–C7 are implemented.

| ID | Work | Citation | Warning |
|----|------|----------|---------|
| W2 | *Ratchet: A Minimal Hygiene Recipe for Self-Evolving LLM Agents* | Zhang, Cui, Wang, et al., 2026. [arXiv:2605.22148](https://arxiv.org/abs/2605.22148) | Lifecycle hygiene, not self-authoring, is what compounds. Harsh retirement went *below* the no-skill floor. If Claims become a library, bound the active set. |
| W3 | *The Blind Curator: How a Biased Judge Silently Disables Skill Retirement* | Zhang et al., 2026. [arXiv:2607.07436](https://arxiv.org/abs/2607.07436) | False-pass bias silently disables retirement. Contribution may be computed only from hostile `run_command` metrics, never from an LLM judge. |
| W4 | *Not All Skills Help: Measuring and Repairing Agent Knowledge* | Wang et al., 2026. [arXiv:2606.15390](https://arxiv.org/abs/2606.15390) | Generating a Claim is judgment; keeping it in default context requires causal evidence. |
| W5 | *Dynamic Agent Skills: A Lifecycle Survey and Taxonomy* | 2026. [arXiv:2607.10113](https://arxiv.org/abs/2607.10113) | Flat retrieval degrades at tens–hundreds of items. BFS will get worse the moment writes stay on. GraphFlow/GraphRAG first. |
| W6 | *SkillsBench: Benchmarking how well agent skills work* | Li et al., 2026. [arXiv:2602.12670](https://arxiv.org/abs/2602.12670) | Human-curated skills +16.2pp; LLM-self-generated skills +0.0pp. Do not auto-promote agent-written Claims. |

Related but out of Kaparthy scope (sibling skill-library line, do not import): Voyager ([arXiv:2305.16291](https://arxiv.org/abs/2305.16291)), MUSE-Autoskill ([arXiv:2605.27366](https://arxiv.org/abs/2605.27366)), Experience Compression Spectrum ([arXiv:2604.15877](https://arxiv.org/abs/2604.15877)), AReaL2.0 / agentic online RL ([arXiv:2607.01120](https://arxiv.org/abs/2607.01120)).

---

## 7. Declined — do not cite as architecture authority

| ID | Artifact | Why declined |
|----|----------|--------------|
| D1 | Viral “Graph Engineering 1000x / Anthropic Playbook” PDFs (Jul 2026 compilations) | Independent synthesis, not affiliated with Karpathy or Anthropic; no measurements; restates F1–F8. Cite primaries or the in-repo technical note (F9). |
| D2 | “Andrew Ng / 4 Steps — Loop to Graph Engineering” one-pagers | Same compilation family; not endorsed. |
| D3 | AI Scientist paper-writing / self-review as the keep signal | Evaluation theater. Rejected in Phase 4.5 (ADR-004). |
| D4 | Agentic online RL weight-update loops | Out of scope. Kaparthy does not train the base model. |
| D5 | Unbounded Voyager-style skill growth inside this repo | Wrong product. Kaparthy emits lineage and sealed metrics. |

---

## 8. Recommended Phase-6 reading order

Read before proposing an ADR. Implementation still needs a contract delta.

```text
1. C6 PACE + C7 sealed holdout      -> keep gate cannot be gamed by one lucky seed
2. C4 SemDeDup on hypotheses/diffs  -> DAG frontier stops repeating itself
3. C1 / C3 tree manager + surprise  -> agent proposes from leaves, not the grid
4. C13 GraphRAG community summaries -> context pack becomes a briefing
5. C12 GraphFlow retrieval          -> INV-12 still holds; relevance replaces hop count
6. C8 standing release gates        -> every new capability has a failing test first
7. Only then: optional KG writes    -> Claims gated by hostile metric + contribution
```

If only four papers are read: **C6, C7, C1, C12**.

---

## 9. Collection log

| Date | What was added | Authority |
|------|----------------|-----------|
| 2026-07-28 | F1–F10 recorded in Master Plan §2 / §12 | IT Architect |
| 2026-08-12 | C1–C14, W1–W6, D1–D5 collected against Phase-5 architecture and named Phase-6 gaps | IT Architect |

New entries require: a stable identifier, a primary URL, a layer mapping, and an explicit steal / do-not-steal or warning line. Viral compilations go in §7 or not at all.

---

**End of bibliography**
