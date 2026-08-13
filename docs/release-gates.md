# Standing release gates (WP6 / C8)

**Source of truth for CI:** `pytest -m release_gate`  
**Human index:** this file  
**Rule:** a new capability merges only if it adds a named failing gate first, then turns it green, and the rest of this suite stays green. No skip without an ADR.

| Gate id | Test | Invariant |
|---------|------|-----------|
| G-INV-01 | `test_protected_path_rejected_before_commit` | INV-01 |
| G-INV-01b | `test_mutable_allowlist_rejects_extra_files` | INV-01 |
| G-INV-02 | `test_metric_override_cannot_keep` | INV-02 |
| G-INV-02b | `test_fake_print_uses_last_match` | INV-02 |
| G-INV-03 | `test_crash_mid_training_reverts_and_logs` | INV-03 |
| G-SEED | `test_seed_not_in_context_or_program` | C7 |
| G-PACE | `test_lucky_single_seed_does_not_keep` | C6 |
| G-CERT | `test_keep_writes_certificate` | C6/C9 |
| G-HOLD | `test_agent_cannot_author_holdout` | C7 |
| G-DUP | `test_duplicate_hparams_rejected` | C4 |
| G-LEAF | `test_nonbest_parent_keep_vs_global` | INV-02 + C1 |
| G-EVID | `test_reverted_commit_is_hub_leaf` | INV-08 |
| G-PACK | `test_context_pack_includes_essentials_and_budget` | INV-12 |
| G-BRF | `test_briefing_does_not_drop_essentials` | C13 |
| G-FLOW | `test_subgraph_diverse_under_budget` | C12 |
| G-HUM | `test_agent_cannot_project_or_write_graph_by_default` | KG humility |
| G-DAG | `test_three_concurrent_agents_divergent_children` | Layer 2 |
| G-REC | `test_recover_after_dirty_tree` | Recovery |
| G-AUTH | `test_require_auth_blocks_anonymous` | Auth |

A release is `release-gates` green + Phase 5 health (`GET /ready`).
