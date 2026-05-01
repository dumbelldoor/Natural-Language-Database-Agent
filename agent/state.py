from typing import TypedDict, Optional, Any, List

class AgentState(TypedDict):
    # Input
    user_query: str

    # Data source: "postgres" (default) or "upload" (user-provided file via DuckDB)
    data_source: str
    upload_session_id: Optional[str]

    # RAG Context
    schemas: str
    few_shot_examples: str

    # Generation & Self-Correction
    generated_sql: str
    execution_error: Optional[str]
    correction_attempts: int

    # Human-In-The-Loop (HITL) Security
    requires_approval: bool
    is_approved: bool

    # Output
    final_results: Optional[List[dict[str, Any]]]
    execution_metrics: Optional[List[str]]
    final_answer: str
    chart_config: Optional[dict[str, Any]]
