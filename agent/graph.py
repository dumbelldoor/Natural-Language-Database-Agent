from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import (
    retrieve_schema,
    generate_sql,
    check_approval,
    execute_sql,
    generate_final_response
)

# 1. Initialize the Graph with our specific State
workflow = StateGraph(AgentState)

# 2. Add all the nodes (the functions we wrote)
workflow.add_node("retrieve_schema", retrieve_schema)
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("check_approval", check_approval)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("generate_final_response", generate_final_response)

# 3. Define the Routing Logic (Conditional Edges)

def route_after_approval(state: AgentState) -> str:
    """Decides whether to execute the SQL or pause for human approval."""
    if state.get("requires_approval") and not state.get("is_approved"):
        print("-> [Router] Halting execution for human approval.")
        return END # Pause the graph until the user approves
    print("-> [Router] Query is safe or approved. Moving to execution.")
    return "execute_sql"

def route_after_execution(state: AgentState) -> str:
    """Decides whether to self-correct an error or formulate the final response."""
    error = state.get("execution_error")
    attempts = state.get("correction_attempts", 0)
    
    if error:
        if attempts < 3:
            print(f"-> [Router] Error detected. Initiating self-correction (Attempt {attempts + 1}/3).")
            return "generate_sql"
        else:
            print("-> [Router] Max correction attempts reached. Failing gracefully.")
            return "generate_final_response" # Will generate a response explaining the failure
            
    print("-> [Router] Execution successful. Moving to final response.")
    return "generate_final_response"

# 4. Wire the standard edges (The fixed path)
workflow.add_edge(START, "retrieve_schema")
workflow.add_edge("retrieve_schema", "generate_sql")
workflow.add_edge("generate_sql", "check_approval")

# 5. Wire the conditional edges (The decision paths)
workflow.add_conditional_edges("check_approval", route_after_approval)
workflow.add_conditional_edges("execute_sql", route_after_execution)

# 6. Finish the loop
workflow.add_edge("generate_final_response", END)

# Compile the graph into an executable application
mcp_agent = workflow.compile()

# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\nTesting LangGraph Orchestration...")
    
    # Let's test an end-to-end safe query (no HITL required)
    initial_state = {
        "user_query": "What are the names of all our products?",
        "correction_attempts": 0,
        "is_approved": False
    }
    
    print("\n--- Starting Graph Run ---")
    final_state = mcp_agent.invoke(initial_state)
    
    print("\n--- Final Output ---")
    print(final_state.get("final_answer"))