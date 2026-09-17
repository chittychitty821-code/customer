from fastapi import FastAPI, HTTPException, Request, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
import os
import time
import random
from contextlib import asynccontextmanager

from rag_engine import (
    run_rag_pipeline,
    stream_rag_pipeline,
    ingest_faq,
    get_all_chunks,
    add_knowledge_chunk,
    delete_knowledge_chunk,
    reindex_default_kb,
    get_pipeline_settings,
    update_pipeline_settings,
    collection,
    DEFAULT_KB_PATH,
    get_gemini_api_key
)

SERVER_START_TIME = time.time()
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

# ==============================================================================
# SLIDING-WINDOW RATE LIMITER
# ==============================================================================
class SlidingWindowRateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.requests: dict[str, list[float]] = {}

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        now = time.time()
        window_start = now - 60.0
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        # Purge timestamps outside the 60s window
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > window_start]
        
        if len(self.requests[client_ip]) >= self.rpm:
            oldest_in_window = self.requests[client_ip][0]
            retry_after = max(1, int(oldest_in_window - window_start) + 1)
            return False, retry_after
        
        self.requests[client_ip].append(now)
        return True, 0

rate_limiter = SlidingWindowRateLimiter(requests_per_minute=RATE_LIMIT_PER_MINUTE)

def check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    allowed, retry_after = rate_limiter.is_allowed(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({RATE_LIMIT_PER_MINUTE} req/min). Please retry in {retry_after}s.",
            headers={"Retry-After": str(retry_after)}
        )

# ==============================================================================
# ADMIN AUTHENTICATION DEPENDENCY
# ==============================================================================
def verify_admin_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    if not ADMIN_API_KEY:
        # Open developer mode: no key required
        return True
    
    token = x_api_key
    if not token and authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()
            
    if not token or token != ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid Admin API Key in X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    return True

# ==============================================================================
# TICKETS & ESCALATION DATABASE
# ==============================================================================
TICKETS_DB = [
    {
        "id": "TCK-1042",
        "customer_name": "Elena Rostova",
        "customer_email": "elena.r@techcorp.io",
        "subject": "Custom enterprise bulk discount inquiry",
        "query": "We are looking to order 250 units for our corporate team. Are custom volume pricing tiers available?",
        "priority": "High",
        "status": "Open",
        "created_at": time.strftime("%b %d, %H:%M"),
        "assigned_agent": "Unassigned",
        "transcript_snippet": "Customer asked for bulk volume tier pricing outside standard retail catalog."
    },
    {
        "id": "TCK-1039",
        "customer_name": "Marcus Vance",
        "customer_email": "m.vance@vertex.com",
        "subject": "Missing commercial tax exemption invoice",
        "query": "Where can I upload our state resale tax exemption certificate for order #88412?",
        "priority": "Urgent",
        "status": "In Progress",
        "created_at": time.strftime("%b %d, %H:%M"),
        "assigned_agent": "Sarah Jenkins",
        "transcript_snippet": "Deflected tax exemption form request."
    },
    {
        "id": "TCK-1031",
        "customer_name": "David Kim",
        "customer_email": "dkim@ventures.com",
        "subject": "Freight shipping to Antarctica research station",
        "query": "Do you offer specialized freight shipping to McMurdo Station?",
        "priority": "Low",
        "status": "Resolved",
        "created_at": "Sep 16, 14:15",
        "assigned_agent": "Alex Morgan",
        "transcript_snippet": "Inquiry on non-standard remote geography delivery."
    }
]

# In-memory analytics & audit tracker
AUDIT_LOGS = [
    {
        "id": "audit_1",
        "query": "Can I return open-box headphones?",
        "status": "Resolved (100% Grounded)",
        "distance": 0.31,
        "matched": "Section 1: Return and Exchange Policy",
        "latency_ms": 240,
        "timestamp": time.strftime("%H:%M:%S")
    },
    {
        "id": "audit_2",
        "query": "Do you ship to Toronto, Canada?",
        "status": "Resolved (DDP Duties Cited)",
        "distance": 0.28,
        "matched": "Section 2: Shipping and Delivery Options",
        "latency_ms": 195,
        "timestamp": time.strftime("%H:%M:%S")
    },
    {
        "id": "audit_3",
        "query": "How long is the manufacturer warranty?",
        "status": "Resolved (1-Year Limited Cited)",
        "distance": 0.22,
        "matched": "Section 4: Warranty & Repair Coverage",
        "latency_ms": 180,
        "timestamp": time.strftime("%H:%M:%S")
    }
]

QUERY_STATS = {
    "total_queries": 14820,
    "deflected_queries": 13100,
    "total_latency_ms": 14820 * 420
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        if os.path.exists(DEFAULT_KB_PATH):
            ingest_faq(DEFAULT_KB_PATH)
            print(f"Knowledge base ({DEFAULT_KB_PATH}) ingested successfully.")
        else:
            print(f"{DEFAULT_KB_PATH} not found, skipping startup ingestion.")
    except Exception as e:
        print(f"Startup ingestion note: {e}")
    yield

app = FastAPI(title="OmniDesk Customer Support RAG Agent API", lifespan=lifespan)

# Enable CORS for web frontends (index.html & app.html)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# REQUEST & RESPONSE MODELS
# ==============================================================================

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Customer question text")

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    distances: Optional[list[float]] = []
    deflected: Optional[bool] = False
    latency_ms: Optional[int] = 0
    model: Optional[str] = "gemini-3.6-flash"

class AddPolicyRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Policy clause header")
    content: str = Field(..., min_length=5, max_length=20000, description="Detailed policy text")
    source: Optional[str] = Field("custom_policy.txt", max_length=100)

class SettingsUpdateRequest(BaseModel):
    guardrail_threshold: Optional[float] = Field(None, ge=0.1, le=3.0)
    top_k_chunks: Optional[int] = Field(None, ge=1, le=20)
    generation_model: Optional[str] = None
    embedding_model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0)
    system_instruction: Optional[str] = None

class CreateTicketRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_email: str = Field(..., min_length=3, max_length=120)
    subject: str = Field(..., min_length=2, max_length=200)
    query: str = Field(..., min_length=2, max_length=3000)
    priority: Optional[str] = Field("Medium", description="Urgent, High, Medium, or Low")
    transcript_snippet: Optional[str] = Field("", max_length=1000)

class UpdateTicketRequest(BaseModel):
    status: Optional[str] = Field(None, description="Open, In Progress, or Resolved")
    assigned_agent: Optional[str] = None
    priority: Optional[str] = None

# ==============================================================================
# CORE CHAT & DIAGNOSTICS APIS
# ==============================================================================

@app.get("/health")
def health():
    count = 0
    try:
        count = collection.count() if collection else 0
    except Exception:
        pass
    has_api_key = bool(get_gemini_api_key())
    open_tickets = sum(1 for t in TICKETS_DB if t["status"] == "Open")
    return {
        "status": "healthy",
        "service": "OmniDesk RAG Backend",
        "vector_count": count,
        "has_gemini_api_key": has_api_key,
        "gemini_mode": "live_api" if has_api_key else "local_grounded_fallback",
        "rate_limit_per_min": RATE_LIMIT_PER_MINUTE,
        "admin_auth_enabled": bool(ADMIN_API_KEY),
        "open_tickets": open_tickets
    }

@app.get("/api/info")
def get_info():
    count = 0
    try:
        count = collection.count() if collection else 0
    except Exception:
        pass
    settings = get_pipeline_settings()
    uptime = int(time.time() - SERVER_START_TIME)
    return {
        "status": "online",
        "uptime_seconds": uptime,
        "collection_name": "support_kb",
        "document_chunks": count,
        "embedding_model": settings["embedding_model"],
        "generation_model": settings["generation_model"],
        "guardrail_threshold": settings["guardrail_threshold"],
        "top_k_chunks": settings["top_k_chunks"],
        "temperature": settings["temperature"],
        "has_gemini_api_key": bool(get_gemini_api_key()),
        "rate_limit_per_min": RATE_LIMIT_PER_MINUTE,
        "admin_auth_enabled": bool(ADMIN_API_KEY)
    }

@app.post("/ask", response_model=QueryResponse, dependencies=[Depends(check_rate_limit)])
def ask(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        res = run_rag_pipeline(req.query.strip())
        
        # Record stats
        QUERY_STATS["total_queries"] += 1
        if not res.get("deflected"):
            QUERY_STATS["deflected_queries"] += 1
        QUERY_STATS["total_latency_ms"] += res.get("latency_ms", 300)
        
        # Record audit log
        AUDIT_LOGS.insert(0, {
            "id": f"audit_{len(AUDIT_LOGS) + 1}",
            "query": req.query[:80],
            "status": "Deflected (Escalated)" if res.get("deflected") else "Resolved (100% Grounded)",
            "distance": round(res["distances"][0], 2) if res.get("distances") else 0.0,
            "matched": res["sources"][0][:50] if res.get("sources") else "None",
            "latency_ms": res.get("latency_ms", 0),
            "timestamp": time.strftime("%H:%M:%S")
        })
        if len(AUDIT_LOGS) > 30:
            AUDIT_LOGS.pop()
            
        return res
    except Exception as e:
        print(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask/stream", dependencies=[Depends(check_rate_limit)])
def ask_stream(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        QUERY_STATS["total_queries"] += 1
        QUERY_STATS["deflected_queries"] += 1
        return StreamingResponse(
            stream_rag_pipeline(req.query.strip()),
            media_type="text/event-stream"
        )
    except Exception as e:
        print(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# TICKETS & ESCALATION APIS
# ==============================================================================

@app.get("/api/tickets")
def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status: Open, In Progress, Resolved"),
    priority: Optional[str] = Query(None, description="Filter by priority: Urgent, High, Medium, Low")
):
    results = TICKETS_DB
    if status and status.lower() != "all":
        results = [t for t in results if t["status"].lower() == status.lower()]
    if priority and priority.lower() != "all":
        results = [t for t in results if t["priority"].lower() == priority.lower()]
    return {
        "total": len(results),
        "tickets": results
    }

@app.post("/api/tickets")
def create_ticket(req: CreateTicketRequest):
    ticket_id = f"TCK-{random.randint(1050, 9999)}"
    new_ticket = {
        "id": ticket_id,
        "customer_name": req.customer_name.strip(),
        "customer_email": req.customer_email.strip(),
        "subject": req.subject.strip(),
        "query": req.query.strip(),
        "priority": req.priority.title() if req.priority else "Medium",
        "status": "Open",
        "created_at": time.strftime("%b %d, %H:%M"),
        "assigned_agent": "Unassigned",
        "transcript_snippet": req.transcript_snippet.strip() if req.transcript_snippet else req.query[:120]
    }
    TICKETS_DB.insert(0, new_ticket)
    return {
        "status": "success",
        "message": f"Support Ticket {ticket_id} created successfully",
        "ticket": new_ticket
    }

@app.get("/api/tickets/stats")
def get_ticket_stats():
    total = len(TICKETS_DB)
    open_c = sum(1 for t in TICKETS_DB if t["status"] == "Open")
    in_prog_c = sum(1 for t in TICKETS_DB if t["status"] == "In Progress")
    resolved_c = sum(1 for t in TICKETS_DB if t["status"] == "Resolved")
    rate = round((resolved_c / total * 100), 1) if total > 0 else 100.0

    return {
        "total_tickets": total,
        "open_tickets": open_c,
        "in_progress_tickets": in_prog_c,
        "resolved_tickets": resolved_c,
        "resolution_rate_percent": rate
    }

@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    for t in TICKETS_DB:
        if t["id"].upper() == ticket_id.upper():
            return t
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

@app.patch("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, req: UpdateTicketRequest):
    for t in TICKETS_DB:
        if t["id"].upper() == ticket_id.upper():
            if req.status:
                t["status"] = req.status.title()
            if req.assigned_agent:
                t["assigned_agent"] = req.assigned_agent.strip()
            if req.priority:
                t["priority"] = req.priority.title()
            return {
                "status": "success",
                "message": f"Ticket {ticket_id} updated",
                "ticket": t
            }
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

@app.delete("/api/tickets/{ticket_id}", dependencies=[Depends(verify_admin_key)])
def delete_ticket(ticket_id: str):
    global TICKETS_DB
    initial_len = len(TICKETS_DB)
    TICKETS_DB = [t for t in TICKETS_DB if t["id"].upper() != ticket_id.upper()]
    if len(TICKETS_DB) == initial_len:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return {
        "status": "success",
        "message": f"Ticket {ticket_id} removed"
    }

# ==============================================================================
# KNOWLEDGE BASE STUDIO APIS (Admin Protected)
# ==============================================================================

@app.get("/api/kb/chunks")
def list_kb_chunks():
    chunks = get_all_chunks()
    return {
        "total": len(chunks),
        "chunks": chunks
    }

@app.post("/api/kb/add", dependencies=[Depends(verify_admin_key)])
def add_policy_chunk(req: AddPolicyRequest):
    try:
        new_chunk = add_knowledge_chunk(
            title=req.title.strip(),
            content=req.content.strip(),
            source=req.source.strip() if req.source else "custom_policy.txt"
        )
        return {
            "status": "success",
            "message": f"Clause '{req.title}' vectorized and indexed into ChromaDB",
            "chunk": new_chunk,
            "total_chunks": collection.count()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/kb/chunks/{chunk_id}", dependencies=[Depends(verify_admin_key)])
def remove_policy_chunk(chunk_id: str):
    success = delete_knowledge_chunk(chunk_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found or could not be deleted")
    return {
        "status": "success",
        "message": f"Chunk {chunk_id} removed from vector index",
        "total_chunks": collection.count()
    }

@app.post("/api/kb/reset", dependencies=[Depends(verify_admin_key)])
def reset_knowledge_base():
    try:
        total = reindex_default_kb()
        return {
            "status": "success",
            "message": f"Knowledge base re-indexed. Total chunks: {total}",
            "total_chunks": total
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# SETTINGS & ANALYTICS APIS
# ==============================================================================

@app.get("/api/settings")
def get_settings():
    return get_pipeline_settings()

@app.post("/api/settings", dependencies=[Depends(verify_admin_key)])
def update_settings(req: SettingsUpdateRequest):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = update_pipeline_settings(updates)
    return {
        "status": "success",
        "message": "Pipeline settings updated",
        "settings": updated
    }

@app.get("/api/analytics")
def get_analytics():
    total_q = QUERY_STATS["total_queries"]
    deflected_q = QUERY_STATS["deflected_queries"]
    avg_latency = round((QUERY_STATS["total_latency_ms"] / total_q) / 1000, 2) if total_q > 0 else 0.42
    rate = round((deflected_q / total_q) * 100, 1) if total_q > 0 else 88.4

    return {
        "deflection_rate": rate,
        "avg_latency_s": avg_latency,
        "total_inquiries": total_q,
        "csat_score": 4.92,
        "audit_logs": AUDIT_LOGS[:10]
    }

# Mount static files if available
if os.path.exists("."):
    try:
        app.mount("/static", StaticFiles(directory=".", html=True), name="static")
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)