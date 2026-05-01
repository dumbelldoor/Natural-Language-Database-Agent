#!/bin/bash
# ============================================================
# NL-to-SQL Agent — One-command startup
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        NL-to-SQL Agent — Starting up         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. Check PostgreSQL is reachable
echo "▶ Checking PostgreSQL..."
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from database.connection import engine
from sqlalchemy import text
with engine.connect() as c:
    c.execute(text('SELECT 1'))
print('  ✅ PostgreSQL connected')
" || { echo "  ❌ PostgreSQL not reachable. Start it with: /usr/local/opt/postgresql@18/bin/pg_ctl -D /usr/local/var/postgresql@18 start"; exit 1; }

# 2. Kill any previous server processes on ports 8000 and 5174
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "  ♻  Cleared port 8000" || true
lsof -ti:5174 | xargs kill -9 2>/dev/null && echo "  ♻  Cleared port 5174" || true

# 3. Start FastAPI backend
echo ""
echo "▶ Starting FastAPI backend on http://localhost:8000 ..."
TOKENIZERS_PARALLELISM=false python3 -m uvicorn api:app \
    --host 0.0.0.0 --port 8000 --log-level warning > /tmp/nl2sql_api.log 2>&1 &
API_PID=$!

# Wait for API to be ready
for i in {1..20}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  ✅ API ready (PID $API_PID)"
        break
    fi
    sleep 1
done

# 4. Start React frontend
echo ""
echo "▶ Starting React frontend on http://localhost:5174 ..."
cd "$PROJECT_DIR/frontend"
npm run dev -- --port 5174 > /tmp/nl2sql_frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 4
echo "  ✅ Frontend ready (PID $FRONTEND_PID)"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅  All services running!                    ║"
echo "║                                              ║"
echo "║  Frontend:  http://localhost:5174            ║"
echo "║  API:       http://localhost:8000            ║"
echo "║  API Docs:  http://localhost:8000/docs       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

# Open the browser
open http://localhost:5174 2>/dev/null || true

# Keep script alive and kill children on exit
trap "echo ''; echo 'Stopping...'; kill $API_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
