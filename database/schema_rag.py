from sqlalchemy import text
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from database.connection import engine
from config import RAG_CONFIG

# Initialize Embedding model via central config
EMBEDDING_MODEL = RAG_CONFIG.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

def extract_database_schema() -> list[Document]:
    """
    Connects to PostgreSQL, extracts the table names and column details,
    and formats them as LangChain Documents for the vector store.
    """
    documents = []
    try:
        with engine.connect() as conn:
            # 1. Get all public tables
            tables_query = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
            tables = conn.execute(tables_query).fetchall()

            # 2. For each table, get its columns and data types
            for table in tables:
                table_name = table[0]
                columns_query = text(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}';
                """)
                columns = conn.execute(columns_query).fetchall()
                
                # 3. Format into a clean text string for the LLM
                schema_text = f"Table Name: {table_name}\nColumns:\n"
                for col in columns:
                    schema_text += f" - {col[0]} ({col[1]})\n"
                
                # 4. Create a LangChain Document
                doc = Document(page_content=schema_text, metadata={"table_name": table_name})
                documents.append(doc)
                
        return documents
    except Exception as e:
        print(f"Error extracting schema: {e}")
        return []

def create_schema_vector_store() -> FAISS:
    """
    Embeds the extracted database schemas into a local FAISS vector store.
    """
    docs = extract_database_schema()
    if not docs:
        raise ValueError("No schema documents found. Is the database empty?")
    
    # Create and return the FAISS vector store
    vector_store = FAISS.from_documents(docs, embeddings)
    return vector_store

# Initialize the vector store in memory when this module is loaded
print("Initializing local FAISS vector store with DB schemas...")
schema_vector_store = create_schema_vector_store()

def get_relevant_schemas(user_query: str, k: int = 2) -> str:
    """
    Takes a natural language query and returns the DDL/Schema for the top 'k' most relevant tables.
    """
    results = schema_vector_store.similarity_search(user_query, k=k)
    
    combined_schemas = "\n\n".join([doc.page_content for doc in results])
    return combined_schemas

# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\nTesting RAG Schema Retrieval...")
    
    # Test Question 1: Should retrieve 'customers' and 'orders'
    query_1 = "Show me the email addresses of all users who have a pending status."
    print(f"\nUser Query: '{query_1}'")
    print("Retrieved Schemas:")
    print("-" * 40)
    print(get_relevant_schemas(query_1, k=2))
    
    # Test Question 2: Should retrieve 'products' and 'order_items'
    query_2 = "What is the total stock quantity of all electronics we sell?"
    print(f"\nUser Query: '{query_2}'")
    print("Retrieved Schemas:")
    print("-" * 40)
    print(get_relevant_schemas(query_2, k=1))