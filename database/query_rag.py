import json
import os
from dotenv import load_dotenv
load_dotenv(override=True)
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

GOLDEN_QUERIES_PATH = os.path.join(os.path.dirname(__file__), "golden_queries.json")

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("GITHUB_TOKEN"),
    base_url="https://models.inference.ai.azure.com",
)


def create_golden_vector_store() -> FAISS:
    if not os.path.exists(GOLDEN_QUERIES_PATH):
        raise FileNotFoundError(f"Missing golden queries file at {GOLDEN_QUERIES_PATH}")

    with open(GOLDEN_QUERIES_PATH) as f:
        queries_data = json.load(f)

    documents = [
        Document(
            page_content=item["natural_language_query"],
            metadata={"sql_query": item["sql_query"]},
        )
        for item in queries_data
    ]

    return FAISS.from_documents(documents, embeddings)


_golden_vector_store = None


def _get_store() -> FAISS:
    global _golden_vector_store
    if _golden_vector_store is None:
        print("Initializing golden query vector store (lazy)...")
        _golden_vector_store = create_golden_vector_store()
    return _golden_vector_store


def get_few_shot_examples(user_query: str, k: int = 2) -> str:
    results = _get_store().similarity_search(user_query, k=k)

    if not results:
        return "No historical examples found."

    lines = ["Here are examples of how we write SQL for similar questions:\n"]
    for i, doc in enumerate(results, 1):
        lines.append(f"--- Example {i} ---")
        lines.append(f"User Asked: {doc.page_content}")
        lines.append(f"Correct SQL: {doc.metadata['sql_query']}\n")

    return "\n".join(lines)
