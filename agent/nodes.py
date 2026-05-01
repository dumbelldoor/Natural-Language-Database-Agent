import os
import re
import json
import time
from dotenv import load_dotenv

load_dotenv(override=True)

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agent.state import AgentState
from database.schema_rag import get_relevant_schemas
from database.connection import execute_query
from database.query_rag import get_few_shot_examples
from config import LLM_CONFIG

# ─── LLM client ───────────────────────────────────────────────
llm = ChatOpenAI(
    model=LLM_CONFIG.get("model", "llama-3.3-70b-instruct"),
    api_key=os.getenv("GITHUB_TOKEN"),
    base_url=LLM_CONFIG.get("base_url", "https://models.inference.ai.azure.com"),
    temperature=LLM_CONFIG.get("temperature", 0.0),
    max_tokens=LLM_CONFIG.get("max_tokens", 1024),
)

# ─── Retry helper ─────────────────────────────────────────────
def _invoke_with_retry(chain, inputs: dict, max_retries: int = 3, base_delay: float = 2.0):
    """
    Invoke a LangChain chain with exponential backoff on transient errors.
    Retries on rate-limits (429), server errors (5xx) and connection issues.
    """
    for attempt in range(max_retries):
        try:
            return chain.invoke(inputs)
        except Exception as e:
            err = str(e)
            is_transient = any(code in err for code in ["429", "500", "502", "503", "timeout", "connection"])
            if is_transient and attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)
                print(f"-> [Retry] Attempt {attempt + 1}/{max_retries} failed ({err[:60]}). Retrying in {wait:.0f}s…")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")

# ─── Prompts ──────────────────────────────────────────────────
_SQL_SYSTEM = """You are an expert PostgreSQL query writer. Your ONLY job is to produce a single, \
correct, executable PostgreSQL statement.

STRICT OUTPUT RULES:
- Output ONLY the raw SQL. No markdown fences, no explanation, no preamble.
- End the query with a semicolon.
- Use exact table and column names from the schemas — never invent names.
- Use JOIN conditions based on the Foreign Keys listed in each schema.
- GROUP BY every non-aggregate SELECT column.
- Default LIMIT 500 unless the user specifies otherwise.
- Use LOWER() for case-insensitive string comparisons.
- Use ROUND(..., 2) for monetary values.
- Use DATE_TRUNC / EXTRACT / TO_CHAR for date formatting."""

_SQL_HUMAN = """DATABASE SCHEMAS (columns + foreign keys):
{schemas}

{examples}USER QUESTION: {query}
{error_block}
Write the PostgreSQL query now:"""

_RESPONSE_SYSTEM = """You are a friendly data analyst presenting database query results to a business user.

RULES:
1. Answer the user's question directly in plain English — no SQL, no technical jargon.
2. If the result contains a table of rows, include a clean markdown table (max 20 rows shown).
3. Bold (**) the most important number or insight.
4. Keep prose concise: 1–3 sentences of summary around the table.
5. Do NOT repeat every row in prose — let the table speak.

CHART RULE — append this JSON block at the very end (nothing after it) if the data has \
trends, rankings or comparisons that would benefit from a chart:
```json
{{"chart_type": "bar", "x": "column_name", "y": "column_name"}}
```
Allowed types: "bar", "line", "scatter". Omit the block for single-value or text-only results."""


# ─── Nodes ────────────────────────────────────────────────────

def retrieve_schema(state: AgentState) -> dict:
    """Node 1: Fetch relevant table schemas + few-shot examples."""
    print("-> [retrieve_schema] Finding relevant tables…")
    query = state["user_query"]
    schemas  = get_relevant_schemas(query, k=6)
    examples = get_few_shot_examples(query, k=2)
    return {"schemas": schemas, "few_shot_examples": examples}


def generate_sql(state: AgentState) -> dict:
    """Node 2: Generate a PostgreSQL query with LLM (retry-safe)."""
    print("-> [generate_sql] Writing query…")
    query    = state["user_query"]
    schemas  = state["schemas"]
    examples = state.get("few_shot_examples", "")
    error    = state.get("execution_error")

    examples_block = ""
    if examples and examples != "No historical examples found.":
        examples_block = f"SIMILAR QUERY EXAMPLES:\n{examples}\n\n"

    error_block = ""
    if error:
        print(f"-> [Self-Correction] Previous error: {error}")
        error_block = (
            f"\nPREVIOUS ATTEMPT FAILED:\n{error}\n"
            "Fix the query. Do not repeat the same mistake."
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", _SQL_SYSTEM),
        ("human",  _SQL_HUMAN),
    ])
    chain = prompt | llm

    response = _invoke_with_retry(chain, {
        "schemas":     schemas,
        "examples":    examples_block,
        "query":       query,
        "error_block": error_block,
    })

    sql = response.content.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql).strip()

    return {"generated_sql": sql, "execution_error": None}


def check_approval(state: AgentState) -> dict:
    """Node 3: HITL — detect & dry-run modifying queries."""
    sql = state.get("generated_sql", "").strip()

    modifying = re.compile(
        r'\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|REPLACE|GRANT|REVOKE)\b',
        re.IGNORECASE
    )
    if not modifying.search(sql) or state.get("is_approved"):
        return {"requires_approval": False}

    print("-> [check_approval] Modifying query detected. Dry-running…")
    from database.connection import dry_run_query
    result = dry_run_query(sql)

    if result.get("status") == "error":
        print(f"-> [check_approval] Dry-run failed — routing to self-correction.")
        return {"requires_approval": False}

    annotated = f"-- {result.get('message', 'Dry run OK')}\n{sql}"
    return {"requires_approval": True, "generated_sql": annotated}


def execute_sql(state: AgentState) -> dict:
    """Node 4: Execute the SQL query against PostgreSQL."""
    if state.get("requires_approval") and not state.get("is_approved"):
        return {}

    print("-> [execute_sql] Executing query…")
    sql      = state["generated_sql"]
    attempts = state.get("correction_attempts", 0)

    result = execute_query(sql, include_explain=True)

    if result["status"] == "error":
        print(f"-> [execute_sql] DB error: {result['message']}")
        return {"execution_error": result["message"], "correction_attempts": attempts + 1}

    data = result.get("data") or [{"result": result.get("message", "Executed successfully.")}]
    return {
        "final_results":    data,
        "execution_metrics": result.get("execution_plan", []),
        "execution_error":  None,
    }


def generate_final_response(state: AgentState) -> dict:
    """Node 5: Translate raw results into a natural-language answer."""
    print("-> [generate_final_response] Drafting response…")
    query   = state["user_query"]
    error   = state.get("execution_error")

    if error and state.get("correction_attempts", 0) >= 3:
        return {
            "final_answer": (
                f"I was unable to complete this query after 3 attempts.\n\n"
                f"**Last error:**\n```\n{error}\n```\n\n"
                "Please rephrase your question or verify the data exists."
            ),
            "chart_config": None,
        }

    results    = state.get("final_results", [])
    total_rows = len(results)
    trunc_note = ""

    if total_rows > 20:
        results    = results[:20]
        trunc_note = f"\n\n> **Note:** Showing first 20 of **{total_rows}** total rows."

    prompt = ChatPromptTemplate.from_messages([
        ("system", _RESPONSE_SYSTEM),
        ("human",  "USER QUESTION: {query}\n\nDATA ({row_count} rows):\n{results}{trunc_note}"),
    ])
    chain = prompt | llm

    response = _invoke_with_retry(chain, {
        "query":      query,
        "row_count":  total_rows,
        "results":    json.dumps(results, default=str, indent=2),
        "trunc_note": trunc_note,
    })

    content      = response.content
    chart_config = None

    match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            chart_config = json.loads(match.group(1))
            content      = content[:match.start()].strip()
            print("-> [generate_final_response] Chart config extracted.")
        except Exception as e:
            print(f"-> [generate_final_response] Chart parse failed: {e}")

    return {"final_answer": content, "chart_config": chart_config}
