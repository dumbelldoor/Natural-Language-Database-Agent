import os
import hashlib
import time
from datetime import date
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from agent.graph import mcp_agent
from database.connection import engine
from database.duck_executor import create_session, execute_duck_query, get_session_schema

# ── Config ────────────────────────────────────────────────────
ADMIN_TOKEN  = os.getenv("ADMIN_TOKEN", "")
TRIAL_LIMIT  = int(os.getenv("TRIAL_LIMIT", "2"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
MAX_UPLOAD_MB = 10

app = FastAPI(
    title="NL-to-SQL Agent API",
    version="3.0",
    docs_url=None,   # hide swagger in production
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Log table (created once on startup) ───────────────────────
def _init_log_table():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS query_logs (
                id          SERIAL PRIMARY KEY,
                ts          TIMESTAMPTZ DEFAULT NOW(),
                ip_hash     TEXT,
                query       TEXT,
                status      TEXT,
                duration_ms INTEGER,
                data_source TEXT
            )
        """))

try:
    _init_log_table()
except Exception as e:
    print(f"[warn] Could not create log table: {e}")


def _log(ip: str, query: str, status: str, ms: int, src: str = "postgres"):
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:12]
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO query_logs (ip_hash, query, status, duration_ms, data_source) VALUES (:h,:q,:s,:ms,:src)"),
                {"h": ip_hash, "q": query[:500], "s": status, "ms": ms, "src": src},
            )
    except Exception as e:
        print(f"[warn] Log write failed: {e}")


# ── Trial mode ────────────────────────────────────────────────
_trial: dict[str, int] = defaultdict(int)


def _trial_key(ip: str) -> str:
    return f"{hashlib.md5(ip.encode()).hexdigest()[:8]}:{date.today()}"


def _trial_info(ip: str) -> tuple[bool, int]:
    used = _trial[_trial_key(ip)]
    return used < TRIAL_LIMIT, max(0, TRIAL_LIMIT - used)


def _inc_trial(ip: str):
    _trial[_trial_key(ip)] += 1


def _get_ip(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (req.client.host or "unknown")


def _is_admin(req: Request) -> bool:
    return bool(ADMIN_TOKEN and req.headers.get("x-admin-token") == ADMIN_TOKEN)


# ── Models ────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    is_approved: bool = False
    session_id: str | None = None
    data_source: str = "postgres"


class ChatResponse(BaseModel):
    answer: str
    steps: list[str]
    requires_approval: bool
    generated_sql: str | None
    chart_config: dict | None
    data: list[dict] | None
    execution_metrics: list[str] | None
    row_count: int
    trial_used: int
    trial_limit: int


# ── Chat ──────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest, req: Request):
    ip    = _get_ip(req)
    admin = _is_admin(req)

    if not admin:
        allowed, _ = _trial_info(ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Free trial limit of {TRIAL_LIMIT} queries reached for today. Come back tomorrow!",
            )

    start = time.time()
    src   = request.data_source

    try:
        if src == "upload" and request.session_id:
            schema = get_session_schema(request.session_id)
            if not schema:
                raise HTTPException(status_code=400, detail="Upload session expired. Please re-upload your file.")
            initial_state = {
                "user_query": request.query,
                "schemas": schema,
                "correction_attempts": 0,
                "is_approved": False,
                "data_source": "upload",
                "upload_session_id": request.session_id,
            }
        else:
            initial_state = {
                "user_query": request.query,
                "correction_attempts": 0,
                "is_approved": request.is_approved,
                "data_source": "postgres",
            }

        result_state = mcp_agent.invoke(initial_state)
        ms = int((time.time() - start) * 1000)

        if not admin:
            _inc_trial(ip)

        _log(ip, request.query, "ok", ms, src)

    except HTTPException:
        raise
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        _log(ip, request.query, "error", ms, src)
        err = str(e)
        if "429" in err or "rate limit" in err.lower():
            raise HTTPException(status_code=429, detail="AI provider rate limit. Wait a moment and retry.")
        raise HTTPException(status_code=500, detail=f"Agent error: {err}")

    _, remaining = _trial_info(ip) if not admin else (True, TRIAL_LIMIT)
    trial_used   = TRIAL_LIMIT - remaining if not admin else 0

    requires_approval = result_state.get("requires_approval", False)
    is_approved_state = result_state.get("is_approved", False)
    final_results     = result_state.get("final_results") or []

    steps = ["Analyzing intent and selecting relevant tables…", "Generating SQL from schema context…"]
    if requires_approval and not is_approved_state:
        answer = "🛡️ **Security Hold:** This query modifies the database. Please review and approve or reject."
    else:
        steps += ["Executing query against database…", "Translating results to natural language…"]
        answer = result_state.get("final_answer", "No response generated.")

    return ChatResponse(
        answer=answer,
        steps=steps,
        requires_approval=requires_approval and not is_approved_state,
        generated_sql=result_state.get("generated_sql"),
        chart_config=result_state.get("chart_config"),
        data=final_results,
        execution_metrics=result_state.get("execution_metrics") or [],
        row_count=len(final_results),
        trial_used=trial_used,
        trial_limit=TRIAL_LIMIT,
    )


# ── Upload ────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".csv", ".xlsx", ".xls", ".sql"}:
        raise HTTPException(status_code=400, detail="Unsupported type. Allowed: .csv, .xlsx, .xls, .sql")

    content = await file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_MB} MB).")

    import uuid
    session_id = str(uuid.uuid4())
    try:
        result = create_session(session_id, content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    return {"session_id": session_id, **result}


# ── Admin logs ────────────────────────────────────────────────
@app.get("/api/admin/logs")
def get_logs(token: str = "", limit: int = 100, req: Request = None):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Unauthorized")

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT ts, ip_hash, query, status, duration_ms, data_source FROM query_logs ORDER BY id DESC LIMIT :n"),
            {"n": min(limit, 500)},
        ).fetchall()

    cols = ["timestamp", "ip_hash", "query", "status", "duration_ms", "data_source"]
    return {"total": len(rows), "logs": [dict(zip(cols, r)) for r in rows]}


# ── Health ────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
