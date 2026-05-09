from __future__ import annotations

from typing import Any, TypedDict


class ProcessedQuestion(TypedDict, total=False):
    raw: str
    text: str
    keywords: list[str]
    business_terms: list[str]
    metric_hints: list[str]
    dimension_hints: list[str]
    filter_hints: list[str]
    time_hints: list[str]
    assumptions: list[str]


class KnowledgeTable(TypedDict, total=False):
    id: str
    name: str
    business_name: str
    description: str
    aliases: list[str]
    table_type: str
    enabled: bool
    source: str
    verified: bool


class KnowledgeColumn(TypedDict, total=False):
    id: str
    table_name: str
    name: str
    business_name: str
    data_type: str
    description: str
    aliases: list[str]
    semantic_tags: list[str]
    source: str
    verified: bool


class KnowledgeRelationship(TypedDict, total=False):
    id: str
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    relationship_type: str
    description: str
    source: str
    verified: bool


class KnowledgeValueBinding(TypedDict, total=False):
    id: str
    business_term: str
    table_name: str
    column_name: str
    operator: str
    value: Any
    description: str
    source: str
    verified: bool


class KnowledgeBusinessTerm(TypedDict, total=False):
    id: str
    term: str
    description: str
    related_tables: list[str]
    related_columns: list[str]
    related_value_bindings: list[str]
    source: str
    verified: bool


class ProcessedDatabaseKnowledge(TypedDict):
    dialect: str
    tables: list[KnowledgeTable]
    columns: list[KnowledgeColumn]
    relationships: list[KnowledgeRelationship]
    value_bindings: list[KnowledgeValueBinding]
    business_terms: list[KnowledgeBusinessTerm]


class KnowledgeCandidate(TypedDict, total=False):
    kind: str
    knowledge_id: str
    score: float
    matched_terms: list[str]
    retrieval_method: str
    match_source: str
    evidence_text: str
    reason: str
    raw_ref: dict[str, Any]


class KnowledgeRetrievalResult(TypedDict, total=False):
    candidates: list[KnowledgeCandidate]
    warnings: list[str]
    metadata: dict[str, Any]


class SelectedTable(TypedDict, total=False):
    table_name: str
    role: str
    score: float
    matched_terms: list[str]
    reason: str


class RelevantColumn(TypedDict, total=False):
    table_name: str
    column_name: str
    role: str
    score: float
    matched_terms: list[str]
    reason: str


class SelectedRelationship(TypedDict, total=False):
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    reason: str


class SelectedValueBinding(TypedDict, total=False):
    business_term: str
    table_name: str
    column_name: str
    operator: str
    value: Any
    reason: str


class SelectionEvidence(TypedDict, total=False):
    target_type: str
    target_name: str
    evidence_type: str
    matched_terms: list[str]
    source: str
    detail: str


class DroppedCandidate(TypedDict, total=False):
    target_type: str
    target_name: str
    reason: str
    score: float


class SchemaLinkingResult(TypedDict):
    selected_tables: list[SelectedTable]
    relevant_columns: list[RelevantColumn]
    selected_relationships: list[SelectedRelationship]
    value_bindings: list[SelectedValueBinding]
    evidence: list[SelectionEvidence]
    dropped_candidates: list[DroppedCandidate]
    warnings: list[str]


class SqlGenerationQuestion(TypedDict, total=False):
    raw: str
    text: str
    assumptions: list[str]


class SqlGenerationTable(TypedDict, total=False):
    table_name: str
    role: str
    reason: str


class SqlGenerationColumn(TypedDict, total=False):
    table_name: str
    column_name: str
    role: str
    reason: str


class SqlGenerationRelationship(TypedDict, total=False):
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    reason: str


class SqlGenerationSchemaContext(TypedDict):
    dialect: str
    tables: list[SqlGenerationTable]
    columns: list[SqlGenerationColumn]
    relationships: list[SqlGenerationRelationship]
    value_bindings: list[SelectedValueBinding]


class SqlGenerationSemanticContext(TypedDict, total=False):
    business_terms: list[str]
    metric_definitions: list[dict[str, Any]]
    semantic_rules: list[str]
    assumptions: list[str]


class SqlGenerationPolicy(TypedDict):
    readonly_only: bool
    allow_select_star: bool
    require_limit: bool
    default_limit: int


class SqlGenerationOutputContract(TypedDict):
    format: str
    requirements: list[str]


class SqlGenerationContext(TypedDict):
    question: SqlGenerationQuestion
    schema_context: SqlGenerationSchemaContext
    semantic_context: SqlGenerationSemanticContext
    sql_policy: SqlGenerationPolicy
    output_contract: SqlGenerationOutputContract


__all__ = [
    "DroppedCandidate",
    "KnowledgeBusinessTerm",
    "KnowledgeCandidate",
    "KnowledgeColumn",
    "KnowledgeRelationship",
    "KnowledgeRetrievalResult",
    "KnowledgeTable",
    "KnowledgeValueBinding",
    "ProcessedDatabaseKnowledge",
    "ProcessedQuestion",
    "RelevantColumn",
    "SchemaLinkingResult",
    "SelectedRelationship",
    "SelectedTable",
    "SelectedValueBinding",
    "SelectionEvidence",
    "SqlGenerationColumn",
    "SqlGenerationContext",
    "SqlGenerationOutputContract",
    "SqlGenerationPolicy",
    "SqlGenerationQuestion",
    "SqlGenerationRelationship",
    "SqlGenerationSchemaContext",
    "SqlGenerationSemanticContext",
    "SqlGenerationTable",
]
