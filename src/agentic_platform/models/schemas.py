from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class MetricSpec(BaseModel):
    name: str
    direction: Literal["minimize", "maximize"]
    parse_regex: str
    unit: str | None = None


class ComparisonSpec(BaseModel):
    function: Literal["strictly_better", "better_or_equal", "within_epsilon"]
    epsilon: float | None = None


class ControlDocument(BaseModel):
    id: str
    version: str
    objective: str
    protected_paths: list[str]
    metric: MetricSpec
    comparison: ComparisonSpec
    run_command: str
    time_budget_seconds: float
    keep_criteria: str
    escalation_criteria: str
    exhaustion_criteria: str
    mutable_paths: list[str] | None = None
    program_md: str | None = None
    created_at: str | None = None
    created_by: str | None = None


class Trial(BaseModel):
    id: str
    control_document_id: str
    parent_commit: str
    agent_id: str
    hypothesis: str
    status: Literal["proposed", "running", "kept", "reverted", "crash", "rejected"]
    commit_hash: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    wall_time_seconds: float | None = None
    diff_summary: str | None = None
    ledger_entry_uri: str | None = None
    error: str | None = None
    created_at: str | None = None
    finished_at: str | None = None


class CommitNode(BaseModel):
    hash: str
    parents: list[str]
    agent_id: str
    status: Literal["kept", "reverted", "failed", "pending", "evidence"]
    hypothesis: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    bundle_uri: str | None = None
    message: str | None = None
    created_at: str | None = None
    board_post_ids: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    type: Literal[
        "Entity",
        "Claim",
        "Source",
        "Artifact",
        "AgentRun",
        "Evaluation",
        "Commit",
        "Metric",
        "Task",
    ]
    label: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] | None = None


class GraphEdge(BaseModel):
    id: str
    type: Literal[
        "PARENT_OF",
        "PRODUCED",
        "SUPPORTS",
        "CONTRADICTS",
        "ABOUT",
        "EVALUATED_BY",
        "SUPERSEDES",
        "RESOLVED_TO",
        "MENTIONS",
        "DERIVED_FROM",
        "HAS_METRIC",
    ]
    source: str
    target: str
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] | None = None


class ResolutionOp(BaseModel):
    op: Literal["merge", "unmerge"]
    from_id: str
    to_id: str
    evidence: str | None = None
    reversible: bool = True


class GraphUpdate(BaseModel):
    run_id: str
    agent_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    resolution_ops: list[ResolutionOp] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    id: str
    decision: Literal["pass", "fail", "revise"]
    target: str
    rubric: str
    confidence: float
    evidence_edge_ids: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    notes: str | None = None
    run_id: str | None = None
    created_at: str | None = None


class BudgetDeclaration(BaseModel):
    id: str
    max_model_calls: int | None = None
    max_sub_agents: int | None = None
    max_concurrent_workers: int | None = None
    max_tool_calls: int | None = None
    max_tokens: int | None = None
    max_wall_clock_seconds: float | None = None
    max_cost_usd: float | None = None
    max_retries: int | None = None
    max_graph_writes: int | None = None
    min_evidence_for_finalization: int | None = None


class ConsumedResources(BaseModel):
    model_calls: int = 0
    sub_agents: int = 0
    tokens: int = 0
    wall_clock_seconds: float = 0.0
    cost_usd: float = 0.0
    graph_writes: int = 0


class Run(BaseModel):
    id: str
    control_document_id: str
    budget_id: str
    status: Literal[
        "pending",
        "running",
        "completed",
        "failed",
        "budget_exhausted",
        "cancelled",
    ]
    consumed: ConsumedResources
    audit_log_uri: str | None = None
    partial_result: dict[str, Any] | None = None
    stop_reason: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
