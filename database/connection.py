import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from config import DB_CONFIG

# Still load credentials securely from env, but map non-secrets from config
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

DB_HOST = DB_CONFIG.get("host", "localhost")
DB_PORT = DB_CONFIG.get("port", "5432")
DB_NAME = DB_CONFIG.get("dbname", "mcp_agent_db")

# Construct the PostgreSQL connection string
if DB_PASSWORD:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL)

def execute_query(query: str, include_explain: bool = False) -> dict:
    """
    Executes a SQL query. For SELECT queries, returns data and optional EXPLAIN metrics.
    For modifying queries, commits the transaction.
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))
            
            # If it's a modifying query, commit it and return success
            if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP")):
                connection.commit()
                return {"status": "success", "message": "Query executed and committed successfully."}

            # For SELECT queries, fetch the rows
            rows = [dict(row._mapping) for row in result]
            response = {"status": "success", "data": rows}

            # Inject the Performance Metrics (EXPLAIN ANALYZE) if requested
            if include_explain and query.strip().upper().startswith("SELECT"):
                explain_query = f"EXPLAIN ANALYZE {query}"
                explain_result = connection.execute(text(explain_query))
                explain_plan = [row[0] for row in explain_result]
                response["execution_plan"] = explain_plan

            return response

    except SQLAlchemyError as e:
        # We catch errors gracefully so the Agent doesn't crash, allowing it to self-correct
        return {"status": "error", "message": str(e)}

def dry_run_query(query: str) -> dict:
    """
    Executes a SQL query within a strict transaction that is IMMEDIATELY rolled back.
    This ensures no data is actually modified, but allows us to verify syntax and validity
    before we present the human-in-the-loop approval.
    """
    try:
        with engine.connect() as connection:
            # We explicitly start a transaction so we can rollback
            with connection.begin() as transaction:
                result = connection.execute(text(query))
                
                response = {"status": "success", "message": "Dry-run verified successfully. SQL is valid."}
                
                # A rowcount can be useful for human-in-the-loop preview
                if result.rowcount > 0:
                    response["message"] += f" (Would affect {result.rowcount} rows)"
                
                transaction.rollback()  # ALWAYS ROLLBACK!
                return response
    except SQLAlchemyError as e:
        return {"status": "error", "message": str(e)}

# --- TEST BLOCK ---
if __name__ == "__main__":
    print("Testing PostgreSQL connection...")
    
    # Let's test a complex join from our dummy data and ask for the execution plan
    test_sql = """
        SELECT c.first_name, p.product_name, oi.quantity
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN products p ON oi.product_id = p.product_id;
    """
    
    output = execute_query(test_sql, include_explain=True)
    
    import json
    print(json.dumps(output, indent=2))