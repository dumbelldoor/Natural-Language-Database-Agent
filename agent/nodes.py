import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agent.state import AgentState
from database.schema_rag import get_relevant_schemas
from database.connection import execute_query

load_dotenv()

# Initialize Llama 3.3 70B using the free GitHub Models OpenAI-compatible endpoint
llm = ChatOpenAI(
    model="llama-3.3-70b-instruct",
    api_key=os.getenv("GITHUB_TOKEN"),
    base_url="https://models.inference.ai.azure.com", 
    temperature=0, # Temperature 0 ensures deterministic, precise SQL generation
)

def retrieve_schema(state: AgentState) -> dict:
    """Node 1: Retrieves only the necessary table schemas using our FAISS RAG system."""
    print("-> [Node: retrieve_schema] Finding relevant tables...")
    query = state["user_query"]
    schemas = get_relevant_schemas(query, k=3)
    return {"schemas": schemas}

def generate_sql(state: AgentState) -> dict:
    """Node 2: Generates the PostgreSQL query. If it failed previously, it self-corrects."""
    print("-> [Node: generate_sql] Writing PostgreSQL query...")
    query = state["user_query"]
    schemas = state["schemas"]
    error = state.get("execution_error")

    # The prompt dynamically changes if the agent is in a self-correction loop
    prompt_str = """You are an expert Data Engineer writing PostgreSQL queries.
    Based on the following user request and database schemas, write a valid PostgreSQL query.
    Return ONLY the raw SQL query. Do not wrap it in markdown block quotes. Do not explain it.
    
    Schemas:
    {schemas}
    
    User Request: {query}
    """
    if error:
        print(f"-> [Self-Correction] Fixing previous error: {error}")
        prompt_str += f"\nYour previous query failed with this error: {error}\nPlease fix the SQL query."

    prompt = ChatPromptTemplate.from_template(prompt_str)
    chain = prompt | llm
    
    response = chain.invoke({"schemas": schemas, "query": query})
    
    # Strip any accidental markdown formatting the LLM might include
    sql = response.content.strip().replace("```sql", "").replace("```", "").strip()
    
    return {"generated_sql": sql, "execution_error": None}

def check_approval(state: AgentState) -> dict:
    """Node 3: Human-in-the-Loop Security. Detects if the query modifies data."""
    sql = state.get("generated_sql", "").strip().upper()
    is_modifying = any(sql.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"])
    
    if is_modifying and not state.get("is_approved"):
        print("-> [Node: check_approval] WARNING: Modifying query detected. Pausing for Human Approval.")
        return {"requires_approval": True}
    
    return {"requires_approval": False}

def execute_sql(state: AgentState) -> dict:
    """Node 4: Safely executes the SQL and captures EXPLAIN metrics."""
    # Safety catch: Do not execute if it requires approval but isn't approved
    if state.get("requires_approval") and not state.get("is_approved"):
        return {}

    print("-> [Node: execute_sql] Running query on PostgreSQL database...")
    sql = state["generated_sql"]
    attempts = state.get("correction_attempts", 0)

    result = execute_query(sql, include_explain=True)

    # If the database throws an error, we capture it to feed back to the LLM
    if result["status"] == "error":
        print(f"-> [Node: execute_sql] Database Error encountered!")
        return {
            "execution_error": result["message"],
            "correction_attempts": attempts + 1
        }
    
    return {
        "final_results": result.get("data", []),
        "execution_metrics": result.get("execution_plan", []),
        "execution_error": None
    }

def generate_final_response(state: AgentState) -> dict:
    """Node 5: Translates the raw JSON database results into plain English."""
    print("-> [Node: generate_final_response] Translating results to natural language...")
    query = state["user_query"]
    results = state.get("final_results", [])
    
    prompt = ChatPromptTemplate.from_template(
        """You are a helpful AI assistant. 
        The user asked: "{query}"
        The database returned this raw data: {results}
        
        Provide a clear, concise, natural language summary of the results. 
        Do not mention SQL or database metrics. Just give the final answer."""
    )
    chain = prompt | llm
    response = chain.invoke({"query": query, "results": results})
    
    return {"final_answer": response.content}

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