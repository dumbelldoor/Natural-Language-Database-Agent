import json
from mcp.server.fastmcp import FastMCP
from database.connection import execute_query
from database.schema_rag import get_relevant_schemas

# Initialize the FastMCP server
# This name is what will appear when connecting this to Cursor or Claude Desktop
mcp = FastMCP("PostgreSQL-Enterprise-Agent")

@mcp.tool()
def retrieve_schema(natural_language_query: str) -> str:
    """
    Retrieves the exact PostgreSQL database table schemas needed to answer a user's question.
    Always run this tool before writing a SQL query to ensure you have the correct column names and foreign keys.
    """
    # We call the RAG system we built in Phase 5
    schemas = get_relevant_schemas(natural_language_query, k=3)
    return schemas

@mcp.tool()
def query_database(sql_query: str) -> str:
    """
    Executes a PostgreSQL query and returns the data results, performance metrics, or error messages.
    Use this to read from the database.
    """
    # We call the robust execution layer we built in Phase 4
    result = execute_query(sql_query, include_explain=True)
    
    # MCP tools must return strings, so we serialize our dictionary to JSON
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    # MCP servers communicate over stdio, so NO print statements are allowed here!
    mcp.run(transport='stdio')