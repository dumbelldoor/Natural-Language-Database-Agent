from typing import TypedDict, Optional, Any, List

class AgentState(TypedDict):
    """
    This defines the memory/state of our LangGraph agent.
    Every node in the graph will read and update these variables.
    """
    # 1. Input
    user_query: str
    
    # 2. RAG Context
    schemas: str
    
    # 3. Generation & Self-Correction
    generated_sql: str
    execution_error: Optional[str]
    correction_attempts: int
    
    # 4. Human-In-The-Loop (HITL) Security
    requires_approval: bool
    is_approved: bool
    
    # 5. Output Data & Metrics
    final_results: Optional[List[dict[str, Any]]]
    execution_metrics: Optional[List[str]]
    final_answer: str