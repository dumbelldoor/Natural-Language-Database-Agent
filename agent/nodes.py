import os
import re
import json
from dotenv import load_dotenv
load_dotenv(override=True) # This forces Python to use the newly saved token
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agent.state import AgentState
from database.schema_rag import get_relevant_schemas
from database.connection import execute_query
from database.query_rag import get_few_shot_examples
from config import LLM_CONFIG

# Initialize LLM using dynamically loaded configurations
llm = ChatOpenAI(
    model=LLM_CONFIG.get("model", "llama-3.3-70b-instruct"),
    api_key=os.getenv("GITHUB_TOKEN"),
    base_url=LLM_CONFIG.get("base_url", "https://models.inference.ai.azure.com"), 
    temperature=LLM_CONFIG.get("temperature", 0.0),
)

def retrieve_schema(state: AgentState) -> dict:
    """Node 1: Retrieves necessary table schemas AND historical Golden SQL examples."""
    print("-> [Node: retrieve_schema] Finding relevant tables and historical examples...")
    query = state["user_query"]
    
    schemas = get_relevant_schemas(query, k=3)
    examples = get_few_shot_examples(query, k=2)
    
    return {
        "schemas": schemas, 
        "few_shot_examples": examples
    }

def generate_sql(state: AgentState) -> dict:
    """Node 2: Generates the PostgreSQL query using Schemas and Few-Shot Examples."""
    print("-> [Node: generate_sql] Writing PostgreSQL query...")
    query = state["user_query"]
    schemas = state["schemas"]
    examples = state.get("few_shot_examples", "")
    error = state.get("execution_error")

    # The prompt now dynamically injects the Golden Queries
    prompt_str = """You are an expert Data Engineer writing PostgreSQL queries.
    Based on the following user request and database schemas, write a valid PostgreSQL query.
    Return ONLY the raw SQL query. Do not wrap it in markdown block quotes. Do not explain it.
    
    Schemas:
    {schemas}
    
    {examples}
    
    User Request: {query}
    """
    if error:
        print(f"-> [Self-Correction] Fixing previous error: {error}")
        prompt_str += f"\nYour previous query failed with this error: {error}\nPlease fix the SQL query."

    prompt = ChatPromptTemplate.from_template(prompt_str)
    chain = prompt | llm
    
    # We must pass the new 'examples' variable into the chain invocation
    response = chain.invoke({
        "schemas": schemas, 
        "examples": examples, 
        "query": query
    })
    
    sql = response.content.strip().replace("```sql", "").replace("```", "").strip()
    
    return {"generated_sql": sql, "execution_error": None}
def check_approval(state: AgentState) -> dict:
    """Node 3: Human-in-the-Loop Security. Detects if the query modifies data using rigorous regex and verifies syntax with a dry-run."""
    sql = state.get("generated_sql", "").strip()
    
    # Use rigorous Regex with word boundaries for Modifying Keywords
    modifying_keywords_pattern = re.compile(r'\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|REPLACE|GRANT|REVOKE)\b', re.IGNORECASE)
    is_modifying = bool(modifying_keywords_pattern.search(sql))
    
    if is_modifying and not state.get("is_approved"):
        print("-> [Node: check_approval] WARNING: Modifying query detected. Verifying syntactically via dry-run...")
        # Run a Dry-Run Transaction to verify safe syntax before presenting to user
        from database.connection import dry_run_query
        dry_run_result = dry_run_query(sql)
        
        if dry_run_result.get("status") == "error":
            print(f"-> [Node: check_approval] Dry run revealed SQL error ({dry_run_result['message']}). Bypassing human approval to allow auto-correction.")
            return {"requires_approval": False} # The execute_sql node will fail this query and auto-correct!
            
        print("-> [Node: check_approval] Dry-run passed safely. Pausing for Human Approval.")
        state["generated_sql"] = f"-- {dry_run_result.get('message', 'Dry run successful')}\n" + sql 
        return {"requires_approval": True, "generated_sql": state["generated_sql"]}
    
    return {"requires_approval": False}

def execute_sql(state: AgentState) -> dict:
    """Node 4: Safely executes the SQL and captures EXPLAIN metrics."""
    if state.get("requires_approval") and not state.get("is_approved"):
        return {}

    print("-> [Node: execute_sql] Running query on PostgreSQL database...")
    sql = state["generated_sql"]
    attempts = state.get("correction_attempts", 0)

    result = execute_query(sql, include_explain=True)

    if result["status"] == "error":
        print(f"-> [Node: execute_sql] Database Error encountered!")
        return {
            "execution_error": result["message"],
            "correction_attempts": attempts + 1
        }
    
    # FIX: If it's an UPDATE/INSERT, there is no 'data', just a 'message'. 
    # We must pass this message to the LLM so it knows the action succeeded.
    final_data = result.get("data")
    if final_data is None:
        final_data = [{"database_response": result.get("message", "Action executed successfully.")}]
    
    return {
        "final_results": final_data,
        "execution_metrics": result.get("execution_plan", []),
        "execution_error": None
    }

def generate_final_response(state: AgentState) -> dict:
    """Node 5: Translates the raw JSON database results into plain English."""
    print("-> [Node: generate_final_response] Translating results to natural language...")
    query = state["user_query"]
    results = state.get("final_results", [])
    
    # --- THE FIX: PREVENT CONTEXT WINDOW OVERLOAD ---
    total_rows = len(results)
    truncation_note = ""
    
    # If there are more than 15 rows, we slice the list to protect the LLM token limit
    if total_rows > 15:
        results = results[:15]
        truncation_note = f"\n[CRITICAL NOTE: The database returned {total_rows} total rows, but only the top 15 are shown below. You MUST mention in your response that the output is limited to the first 15 out of {total_rows} total records.]"
    
    prompt = ChatPromptTemplate.from_template(
        """You are a helpful AI assistant. 
        The user asked: "{query}"
        The database returned this raw data: {results} {truncation_note}
        
        Provide a clear, concise, natural language summary of the results. 
        Do not mention SQL or database metrics. Just give the final answer.
        
        IMPORTANT DASHBOARD INSTRUCTION:
        If the data returned contains trends over time, categorical comparisons, or numerical distributions that would visually benefit from a chart, you MUST append a JSON block at the very end of your response formatted exactly like this:
        ```json
        {{"chart_type": "bar", "x": "column_name", "y": "column_name"}}
        ```
        Allowed chart_types: "bar", "line", "scatter". Choose the single best one. Do NOT include this JSON if the data is a single value or text that cannot be meaningfully charted."""
    )
    chain = prompt | llm
    
    # Pass the updated variables to the prompt
    response = chain.invoke({
        "query": query, 
        "results": results, 
        "truncation_note": truncation_note
    })
    
    content = response.content
    chart_config = None
    
    # Parse out the optional chart_config JSON block
    match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            chart_config = json.loads(match.group(1))
            content = content[:match.start()].strip() # Clean the UI response
            print("-> [Node: generate_final_response] Chart Config extracted successfully.")
        except Exception as e:
            print(f"-> [Node: generate_final_response] Could not parse chart JSON: {e}")
            
    return {"final_answer": content, "chart_config": chart_config}
# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\nTesting LLM Connection and Node Logic...")
    
    # Let's mock a simple state to test the LLM generation specifically
    mock_state = {
        "user_query": "How many total products do we have in stock?",
        "schemas": "Table Name: products\nColumns:\n - product_id (integer)\n - product_name (character varying)\n - stock_quantity (integer)",
        "execution_error": None,
        "is_approved": False
    }
    
    # Test generation
    output_state = generate_sql(mock_state)
    print(f"\nGenerated SQL: {output_state['generated_sql']}")