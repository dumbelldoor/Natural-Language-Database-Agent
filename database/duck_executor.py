import duckdb
import pandas as pd
import io
import time
import threading
from pathlib import Path

_sessions: dict = {}
_lock = threading.Lock()
SESSION_TTL = 3600  # 1 hour


def _cleanup():
    now = time.time()
    with _lock:
        expired = [k for k, v in _sessions.items() if now - v["last_access"] > SESSION_TTL]
        for k in expired:
            try:
                _sessions[k]["conn"].close()
            except Exception:
                pass
            del _sessions[k]


def get_session_schema(session_id: str) -> str | None:
    with _lock:
        s = _sessions.get(session_id)
        if s:
            s["last_access"] = time.time()
            return s["schema"]
    return None


def create_session(session_id: str, file_bytes: bytes, filename: str) -> dict:
    _cleanup()
    ext = Path(filename).suffix.lower()
    stem = Path(filename).stem.lower()
    table_name = "".join(c if (c.isalnum() or c == "_") else "_" for c in stem)
    if not table_name or not table_name[0].isalpha():
        table_name = "t_" + table_name

    conn = duckdb.connect()

    if ext == ".csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
        conn.register(table_name, df)
        schema = _describe(conn, table_name, len(df))
        sample = df.head(5).to_dict(orient="records")

    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(io.BytesIO(file_bytes))
        conn.register(table_name, df)
        schema = _describe(conn, table_name, len(df))
        sample = df.head(5).to_dict(orient="records")

    elif ext == ".sql":
        sql_text = file_bytes.decode("utf-8", errors="replace")
        conn.execute(sql_text)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        if not tables:
            raise ValueError("No tables found in the SQL file.")
        schema = "\n\n".join(_describe(conn, t, None) for t in tables)
        table_name = tables[0]
        sample = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchdf().to_dict(orient="records")

    else:
        raise ValueError(f"Unsupported file type: {ext}")

    with _lock:
        _sessions[session_id] = {
            "conn": conn,
            "schema": schema,
            "table_name": table_name,
            "last_access": time.time(),
        }

    return {"schema": schema, "sample": sample, "table_name": table_name}


def execute_duck_query(session_id: str, sql: str) -> dict:
    with _lock:
        s = _sessions.get(session_id)
        if not s:
            return {"status": "error", "message": "Session expired. Please re-upload your file."}
        s["last_access"] = time.time()
        conn = s["conn"]

    try:
        df = conn.execute(sql).fetchdf()
        return {"status": "ok", "data": df.to_dict(orient="records")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _describe(conn: duckdb.DuckDBPyConnection, table_name: str, row_count) -> str:
    cols = conn.execute(f'DESCRIBE "{table_name}"').fetchall()
    col_str = ", ".join(f"{c[0]} ({c[1]})" for c in cols)
    rc = f"\nRows: {row_count}" if row_count is not None else ""
    return f"Table: {table_name}\nColumns: {col_str}{rc}"
