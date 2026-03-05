import json
import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# Use the exact same CPU-friendly embedding model as our schema RAG
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GOLDEN_QUERIES_PATH = os.path.join(os.path.dirname(__file__), "golden_queries.json")

def create_golden_vector_store():
    """Reads the JSON file and builds the FAISS vector store in memory."""
    # We remove the print statement here to keep our MCP server logs perfectly clean
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    
    if not os.path.exists(GOLDEN_QUERIES_PATH):
        raise FileNotFoundError(f"Missing ground truth file at {GOLDEN_QUERIES_PATH}")

    with open(GOLDEN_QUERIES_PATH, 'r') as f:
        queries_data = json.load(f)
        
    documents = []
    for item in queries_data:
        # Embed the plain English question to match against user input
        doc = Document(
            page_content=item["natural_language_query"],
            metadata={"sql_query": item["sql_query"]} # Hide the SQL in the metadata payload
        )
        documents.append(doc)
        
    vector_store = FAISS.from_documents(documents, embeddings)
    return vector_store

# Initialize the vector store in memory when this module is loaded
golden_vector_store = create_golden_vector_store()

def get_few_shot_examples(user_query: str, k: int = 2) -> str:
    """
    Finds the most semantically similar historical questions and returns 
    their SQL as a formatted string to inject into the LLM prompt.
    """
    results = golden_vector_store.similarity_search(user_query, k=k)
    
    if not results:
        return "No historical examples found."
        
    formatted_examples = "Here are examples of how we write SQL for similar questions:\n\n"
    for i, doc in enumerate(results, 1):
        formatted_examples += f"--- Example {i} ---\n"
        formatted_examples += f"User Asked: {doc.page_content}\n"
        formatted_examples += f"Correct SQL: {doc.metadata['sql_query']}\n\n"
        
    return formatted_examples.strip()

# --- TEST BLOCK ---
if __name__ == "__main__":
    print("\nTesting Golden Query Retrieval...")
    
    # We will ask a question phrased differently than the JSON file to test semantic matching
    test_query = "Which customers drop the most cash on tech products?"
    
    print(f"User Query: '{test_query}'\n")
    examples = get_few_shot_examples(test_query, k=1)
    print(examples)