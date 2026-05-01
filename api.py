from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.graph import mcp_agent

app = FastAPI(title="NL-to-SQL Agent API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    is_approved: bool = False
    current_state: dict | None = None


class ChatResponse(BaseModel):
    answer: str
    steps: list[str]
    requires_approval: bool
    generated_sql: str | None
    chart_config: dict | None
    data: list[dict] | None
    execution_metrics: list[str] | None
    row_count: int


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if request.current_state and request.is_approved:
        initial_state = request.current_state
        initial_state["is_approved"] = True
    else:
        initial_state = {
            "user_query": request.query,
            "correction_attempts": 0,
            "is_approved": request.is_approved,
        }

    try:
        result_state = mcp_agent.invoke(initial_state)
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "rate limit" in error_str.lower():
            raise HTTPException(
                status_code=429,
                detail="The AI provider has hit its rate limit. Please wait a moment and try again.",
            )
        raise HTTPException(status_code=500, detail=f"Agent error: {error_str}")

    requires_approval = result_state.get("requires_approval", False)
    is_approved = result_state.get("is_approved", False)
    final_results = result_state.get("final_results") or []
    metrics = result_state.get("execution_metrics") or []

    steps = [
        "Analyzing intent and selecting relevant database tables...",
        "Generating PostgreSQL query from schema context...",
    ]

    if requires_approval and not is_approved:
        answer = (
            "🛡️ **Security Hold:** This query modifies the database. "
            "Please review the SQL and approve or reject the action."
        )
    else:
        steps += [
            "Executing query against PostgreSQL database...",
            "Translating results to natural language...",
        ]
        answer = result_state.get("final_answer", "No response generated.")

    return ChatResponse(
        answer=answer,
        steps=steps,
        requires_approval=requires_approval and not is_approved,
        generated_sql=result_state.get("generated_sql"),
        chart_config=result_state.get("chart_config"),
        data=final_results,
        execution_metrics=metrics,
        row_count=len(final_results),
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
