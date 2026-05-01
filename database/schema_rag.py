import os
import hashlib
from dotenv import load_dotenv
load_dotenv(override=True)
from sqlalchemy import text
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from database.connection import engine
from config import RAG_CONFIG

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".faiss_cache")

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key=os.getenv("GITHUB_TOKEN"),
    base_url="https://models.inference.ai.azure.com",
)


def _get_foreign_keys(conn) -> dict[str, list[str]]:
    """Returns a dict mapping table_name -> list of FK description strings."""
    fk_query = text("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = 'public';
    """)
    rows = conn.execute(fk_query).fetchall()
    fk_map: dict[str, list[str]] = {}
    for row in rows:
        table, col, ftable, fcol = row
        fk_map.setdefault(table, []).append(
            f"{col} -> {ftable}.{fcol}"
        )
    return fk_map


def extract_full_schema() -> tuple[list[Document], str]:
    """
    Extracts all table schemas with column types AND foreign key relationships.
    Returns (documents, schema_hash) where the hash can detect schema changes.
    """
    documents = []
    schema_text_all = []

    try:
        with engine.connect() as conn:
            fk_map = _get_foreign_keys(conn)

            tables_result = conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
            ).fetchall()

            for (table_name,) in tables_result:
                cols_result = conn.execute(
                    text("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = :tname
                        ORDER BY ordinal_position;
                    """),
                    {"tname": table_name}
                ).fetchall()

                schema_text = f"Table: {table_name}\nColumns:\n"
                for col_name, data_type, nullable, default in cols_result:
                    nullable_str = "" if nullable == "YES" else " NOT NULL"
                    default_str = f" DEFAULT {default}" if default else ""
                    schema_text += f"  - {col_name} ({data_type}{nullable_str}{default_str})\n"

                fks = fk_map.get(table_name, [])
                if fks:
                    schema_text += "Foreign Keys:\n"
                    for fk in fks:
                        schema_text += f"  - {fk}\n"

                schema_text_all.append(schema_text)
                documents.append(Document(page_content=schema_text, metadata={"table_name": table_name}))

    except Exception as e:
        print(f"Error extracting schema: {e}")
        return [], ""

    combined = "\n".join(schema_text_all)
    schema_hash = hashlib.md5(combined.encode()).hexdigest()
    return documents, schema_hash


def _cache_path(schema_hash: str) -> str:
    return os.path.join(CACHE_DIR, f"schema_{schema_hash}")


def create_schema_vector_store() -> FAISS:
    """
    Builds or loads a cached FAISS index from the live database schema.
    The cache is invalidated automatically when the schema changes.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    docs, schema_hash = extract_full_schema()

    if not docs:
        raise ValueError("No schema documents found. Is the database running and populated?")

    cache_path = _cache_path(schema_hash)

    if os.path.exists(cache_path):
        print(f"Loading cached schema index ({schema_hash[:8]}...).")
        return FAISS.load_local(cache_path, embeddings, allow_dangerous_deserialization=True)

    print(f"Building new schema index ({len(docs)} tables)...")
    vector_store = FAISS.from_documents(docs, embeddings)
    vector_store.save_local(cache_path)
    return vector_store


def get_full_schema_text() -> str:
    """Returns the full schema of all tables as a single string (for small-schema DBs)."""
    docs, _ = extract_full_schema()
    return "\n\n".join(doc.page_content for doc in docs)


_schema_vector_store = None


def _get_store() -> FAISS:
    global _schema_vector_store
    if _schema_vector_store is None:
        print("Initializing schema vector store (lazy)...")
        _schema_vector_store = create_schema_vector_store()
    return _schema_vector_store


def get_relevant_schemas(user_query: str, k: int = 6) -> str:
    """Returns DDL + FK context for the top-k most relevant tables."""
    results = _get_store().similarity_search(user_query, k=k)
    return "\n\n".join(doc.page_content for doc in results)
