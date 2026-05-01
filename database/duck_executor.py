import duckdb
import pandas as pd
import io
import os
import time
import tempfile
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


def _safe_name(name: str) -> str:
    """Sanitize a string into a valid DuckDB identifier (max 50 chars)."""
    cleaned = "".join(c if (c.isalnum() or c == "_") else "_" for c in name.lower())
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "t_" + cleaned
    return cleaned[:50]


def _schema_from_conn(conn: duckdb.DuckDBPyConnection, table_name: str, row_count) -> str:
    """Extract schema using SELECT * LIMIT 0 — works on tables AND views in all DuckDB versions."""
    try:
        result = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 0')
        col_str = ", ".join(f"{d[0]} ({d[1]})" for d in result.description)
    except Exception:
        col_str = "(could not read columns)"
    rc = f"\nRows: {row_count}" if row_count is not None else ""
    return f"Table: {table_name}\nColumns: {col_str}{rc}"


def create_session(session_id: str, file_bytes: bytes, filename: str) -> dict:
    _cleanup()
    ext        = Path(filename).suffix.lower()
    table_name = _safe_name(Path(filename).stem)

    conn     = duckdb.connect()
    tmp_path = None

    try:
        if ext == ".csv":
            # Write to a temp file so DuckDB uses its native auto-detecting CSV reader.
            # This handles encoding (UTF-8, latin-1, windows-1252…), quoting, and delimiters
            # much better than pandas.
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            conn.execute(
                f'CREATE TABLE "{table_name}" AS SELECT * FROM read_csv_auto(?)',
                [tmp_path],
            )
            row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            schema    = _schema_from_conn(conn, table_name, row_count)
            sample    = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchdf().to_dict(orient="records")

        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
            # Sanitize column names — spaces and special chars break SQL references
            df.columns = [_safe_name(str(c)) for c in df.columns]
            # Register then CREATE TABLE so the data is fully materialised inside DuckDB
            conn.register("_upload_df", df)
            conn.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM _upload_df')
            schema = _schema_from_conn(conn, table_name, len(df))
            sample = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchdf().to_dict(orient="records")

        elif ext == ".sql":
            sql_text = file_bytes.decode("utf-8", errors="replace")
            conn.execute(sql_text)
            tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
            if not tables:
                raise ValueError("No tables found in the SQL file.")
            schema     = "\n\n".join(_schema_from_conn(conn, t, None) for t in tables)
            table_name = tables[0]
            sample     = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchdf().to_dict(orient="records")

        else:
            raise ValueError(f"Unsupported file type: {ext}. Use .csv, .xlsx, .xls, or .sql")

    except Exception:
        conn.close()
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    with _lock:
        _sessions[session_id] = {
            "conn":        conn,
            "schema":      schema,
            "table_name":  table_name,
            "last_access": time.time(),
        }

    return {"schema": schema, "sample": sample, "table_name": table_name}


def execute_duck_query(session_id: str, sql: str) -> dict:
    # Grab the connection reference while holding the lock, then execute outside it
    # so we don't block other requests during query execution.
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
