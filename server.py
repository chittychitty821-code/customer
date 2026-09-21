from fastapi import FastAPI, HTTPException, Request, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
import os
import time
import random
import json
import csv
import io
from contextlib import asynccontextmanager

from rag_engine import (
    run_rag_pipeline,
    query_rag_pipeline,
    stream_rag_pipeline,
    classify_intent_and_sentiment,
    generate_agent_reply_draft,
    ingest_faq,
    get_all_chunks,
    add_knowledge_chunk,
    delete_knowledge_chunk,
    reindex_default_kb,
    get_pipeline_settings,
    update_pipeline_settings,
    run_synthetic_benchmark,
    bm25_search,
    hybrid_search_rag,
    analyze_claim_image,
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
        "customer_id": "CUST-8492",
        "customer_name": "Elena Rostova",
        "customer_email": "elena.r@techcorp.io",
        "customer_tier": "VIP Enterprise",
        "intent": "Billing & Payment",
        "sentiment": "VIP / Commercial",
        "subject": "Custom enterprise bulk discount inquiry",
        "query": "We are looking to order 250 units for our corporate team. Are custom volume pricing tiers available?",
        "priority": "High",
        "status": "Open",
        "created_at": time.strftime("%b %d, %H:%M"),
        "created_ts": time.time() - 3600,  # 1 hour ago
        "assigned_agent": "Unassigned",
        "transcript_snippet": "Customer asked for bulk volume tier pricing outside standard retail catalog.",
        "messages": [
            {
                "id": "msg_1",
                "sender": "Elena Rostova",
                "text": "We are looking to order 250 units for our corporate team. Are custom volume pricing tiers available?",
                "is_internal_note": False,
                "timestamp": time.strftime("%b %d, %H:%M")
            }
        ]
    },
    {
        "id": "TCK-1039",
        "customer_id": "CUST-6310",
        "customer_name": "Marcus Vance",
        "customer_email": "m.vance@vertex.com",
        "customer_tier": "Pro Business",
        "intent": "Billing & Payment",
        "sentiment": "High Urgency",
        "subject": "Missing commercial tax exemption invoice",
        "query": "Where can I upload our state resale tax exemption certificate for order #88412?",
        "priority": "Urgent",
        "status": "In Progress",
        "created_at": time.strftime("%b %d, %H:%M"),
        "created_ts": time.time() - 1200,  # 20 mins ago
        "assigned_agent": "Sarah Chen",
        "transcript_snippet": "Deflected tax exemption form request.",
        "messages": [
            {
                "id": "msg_1",
                "sender": "Marcus Vance",
                "text": "Where can I upload our state resale tax exemption certificate for order #88412?",
                "is_internal_note": False,
                "timestamp": time.strftime("%b %d, %H:%M")
            },
            {
                "id": "msg_2",
                "sender": "Sarah Chen",
                "text": "Reviewing order #88412 against the Washington state sales tax exemption registry.",
                "is_internal_note": True,
                "timestamp": time.strftime("%b %d, %H:%M")
            }
        ]
    },
    {
        "id": "TCK-1031",
        "customer_id": "CUST-4195",
        "customer_name": "David Kim",
        "customer_email": "dkim@ventures.com",
        "customer_tier": "Standard Retail",
        "intent": "Shipping & Logistics",
        "sentiment": "Standard",
        "subject": "Freight shipping to Antarctica research station",
        "query": "Do you offer specialized freight shipping to McMurdo Station?",
        "priority": "Low",
        "status": "Resolved",
        "created_at": "Sep 16, 14:15",
        "created_ts": time.time() - 86400,
        "assigned_agent": "Alex Morgan",
        "transcript_snippet": "Inquiry on non-standard remote geography delivery.",
        "messages": [
            {
                "id": "msg_1",
                "sender": "David Kim",
                "text": "Do you offer specialized freight shipping to McMurdo Station?",
                "is_internal_note": False,
                "timestamp": "Sep 16, 14:15"
            },
            {
                "id": "msg_2",
                "sender": "Alex Morgan",
                "text": "Provided freight courier quote via DHL Global Forwarding charter.",
                "is_internal_note": False,
                "timestamp": "Sep 16, 15:30"
            }
        ]
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

# In-memory customer feedback & CSAT tracking
FEEDBACK_DB = [
    {"id": "fb_1", "query": "Can I return open-box items?", "rating": 5, "is_positive": True, "comment": "Clear return policy breakdown!", "language": "English", "timestamp": time.strftime("%H:%M:%S")},
    {"id": "fb_2", "query": "Do you ship to Toronto Canada?", "rating": 5, "is_positive": True, "comment": "DDP customs duties detail was super helpful.", "language": "English", "timestamp": time.strftime("%H:%M:%S")},
    {"id": "fb_3", "query": "¿Cuál es la garantía del producto?", "rating": 5, "is_positive": True, "comment": "Excelente respuesta en español.", "language": "Spanish", "timestamp": time.strftime("%H:%M:%S")}
]

# Standard Agent Response Macros
MACROS_DB = [
    {
        "id": "macro_return_rma",
        "title": "📦 30-Day Return RMA Authorization",
        "category": "Return & Refund",
        "template": "Hi {{customer_name}},\n\nThank you for reaching out to OmniDesk Support. We have approved your return authorization for Ticket #{{ticket_id}} under our 30-Day Policy.\n\nNext Steps:\n1. Affix the prepaid return shipping label to the original packaging.\n2. Drop off at any authorized courier depot within 14 days.\n3. Your full refund will process within 3-5 business days upon arrival.\n\nWarm regards,\n{{assigned_agent}} — OmniDesk Support"
    },
    {
        "id": "macro_warranty_claim",
        "title": "🛡️ 1-Year Manufacturer Warranty Intake",
        "category": "Warranty & Claims",
        "template": "Hi {{customer_name}},\n\nWe have received your warranty inquiry for Ticket #{{ticket_id}}. To process your 1-Year Limited Manufacturer Warranty replacement:\n\n1. Reply with your hardware serial number (on barcode label).\n2. Attach 1-2 clear photos/video of the issue.\n\nOnce received, our warranty desk will expedite your replacement dispatch.\n\nBest regards,\n{{assigned_agent}} — Warranty Desk"
    },
    {
        "id": "macro_price_match",
        "title": "💳 14-Day Price Match Adjustment Credit",
        "category": "Billing & Payment",
        "template": "Hi {{customer_name}},\n\nGreat news! We have verified the promotional pricing under our 14-Day Price Match Guarantee for Ticket #{{ticket_id}}.\n\nA price adjustment credit has been applied to your original payment method and will reflect on your statement in 2-3 business days.\n\nThank you for choosing OmniDesk,\n{{assigned_agent}}"
    },
    {
        "id": "macro_intl_ddp",
        "title": "✈️ DHL International DDP Delivery Details",
        "category": "Shipping & Logistics",
        "template": "Hi {{customer_name}},\n\nRegarding your international delivery inquiry for Ticket #{{ticket_id}}:\n\nAll international shipments are dispatched via DHL Express under Delivered Duty Paid (DDP) terms. All customs duties, VAT, and brokerage fees were pre-cleared at checkout. No additional fees will be requested upon arrival.\n\nTracking updates are active in your account dashboard.\n\nSafe travels & regards,\n{{assigned_agent}}"
    }
]

# Outbound Incident Webhook Logs & Dispatcher
WEBHOOK_LOGS_DB = [
    {
        "id": "wh_101",
        "event_type": "sla_warning",
        "title": "⏱️ SLA Warning (< 30m) — Ticket #TCK-1021",
        "severity": "high",
        "destination": "Slack #support-urgent",
        "payload": {"ticket_id": "TCK-1021", "customer": "Elena Rostova", "tier": "VIP Enterprise", "remaining_minutes": 25},
        "status": "delivered",
        "timestamp": time.strftime("%H:%M:%S")
    },
    {
        "id": "wh_102",
        "event_type": "csat_alert",
        "title": "⚠️ Low CSAT Rating Received (2/5)",
        "severity": "medium",
        "destination": "PagerDuty / Support Leads",
        "payload": {"rating": 2, "query": "How to ship heavy electronics?", "language": "English"},
        "status": "delivered",
        "timestamp": time.strftime("%H:%M:%S")
    }
]

def dispatch_webhook_alert(event_type: str, title: str, payload: dict, severity: str = "medium", destination: str = "Slack #support-alerts") -> dict:
    """Dispatches a simulated Slack / PagerDuty webhook incident alert."""
    log_entry = {
        "id": f"wh_{random.randint(1000, 9999)}",
        "event_type": event_type,
        "title": title,
        "severity": severity,
        "destination": destination,
        "payload": payload,
        "status": "delivered",
        "timestamp": time.strftime("%H:%M:%S")
    }
    WEBHOOK_LOGS_DB.insert(0, log_entry)
    if len(WEBHOOK_LOGS_DB) > 50:
        WEBHOOK_LOGS_DB.pop()
    return log_entry

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
# REQUEST & RESPONSE MODELS
# ==============================================================================

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Customer question text")
    language: Optional[str] = Field("Auto Detect", max_length=50)

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    distances: Optional[list[float]] = []
    deflected: Optional[bool] = False
    latency_ms: Optional[int] = 0
    language: Optional[str] = "English"
    model: Optional[str] = "gemini-3.6-flash"

class FeedbackRequest(BaseModel):
    query: Optional[str] = ""
    rating: int = Field(5, ge=1, le=5)
    is_positive: bool = True
    comment: Optional[str] = ""
    language: Optional[str] = "English"

class ApplyMacroRequest(BaseModel):
    macro_id: str = Field(..., min_length=1)
    sender: Optional[str] = "Support Specialist"

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
    customer_id: Optional[str] = Field(None, max_length=50)
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_email: str = Field(..., min_length=3, max_length=120)
    customer_tier: Optional[str] = Field("Standard Retail", max_length=50)
    subject: str = Field(..., min_length=2, max_length=200)
    query: str = Field(..., min_length=2, max_length=3000)
    priority: Optional[str] = Field("Medium", description="Urgent, High, Medium, or Low")
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    transcript_snippet: Optional[str] = Field("", max_length=1000)

class TicketMessageRequest(BaseModel):
    sender: str = Field("Support Agent", min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=5000)
    is_internal_note: Optional[bool] = False

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
        res = run_rag_pipeline(req.query.strip(), target_language=req.language)
        
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
            stream_rag_pipeline(req.query.strip(), target_language=req.language),
            media_type="text/event-stream"
        )
    except Exception as e:
        print(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# TICKETS, SLA ENGINE & COPILOT APIS
# ==============================================================================

def calculate_sla_details(ticket: dict) -> dict:
    created_ts = ticket.get("created_ts") or time.time()
    priority = (ticket.get("priority") or "Medium").capitalize()
    
    # SLA target window in minutes
    sla_targets = {
        "Urgent": 60,       # 1 hour
        "High": 240,        # 4 hours
        "Medium": 1440,     # 24 hours
        "Low": 2880         # 48 hours
    }
    target_mins = sla_targets.get(priority, 1440)
    elapsed_mins = int((time.time() - created_ts) / 60)
    remaining_mins = target_mins - elapsed_mins
    is_breached = remaining_mins <= 0 and ticket.get("status") != "Resolved"
    
    if ticket.get("status") == "Resolved":
        badge_status = "resolved"
        label = "SLA Met"
    elif is_breached:
        badge_status = "breached"
        label = f"SLA Breached ({abs(remaining_mins)}m overdue)"
    elif remaining_mins <= 60:
        badge_status = "urgent"
        label = f"{remaining_mins}m left"
    elif remaining_mins <= 180:
        badge_status = "warning"
        label = f"{remaining_mins // 60}h {remaining_mins % 60}m left"
    else:
        badge_status = "normal"
        hours = remaining_mins // 60
        label = f"{hours}h left" if hours < 24 else f"{hours // 24}d {hours % 24}h left"
        
    return {
        "sla_target_minutes": target_mins,
        "elapsed_minutes": elapsed_mins,
        "remaining_minutes": max(0, remaining_mins),
        "is_breached": is_breached,
        "badge_status": badge_status,
        "label": label
    }

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
    
    # Calculate live SLA details for each ticket
    enriched = []
    for t in results:
        t_copy = dict(t)
        t_copy["sla_details"] = calculate_sla_details(t)
        enriched.append(t_copy)

    return {
        "total": len(enriched),
        "tickets": enriched
    }

@app.post("/api/tickets")
def create_ticket(req: CreateTicketRequest):
    ticket_id = f"TCK-{random.randint(1050, 9999)}"
    cust_id = req.customer_id.strip() if req.customer_id else f"CUST-{random.randint(1000, 9999)}"
    
    classification = classify_intent_and_sentiment(req.query)
    intent = req.intent.strip() if req.intent else classification["intent"]
    sentiment = req.sentiment.strip() if req.sentiment else classification["sentiment"]
    now_ts = time.time()
    
    initial_messages = [
        {
            "id": "msg_1",
            "sender": req.customer_name.strip(),
            "text": req.query.strip(),
            "is_internal_note": False,
            "timestamp": time.strftime("%b %d, %H:%M")
        }
    ]

    new_ticket = {
        "id": ticket_id,
        "customer_id": cust_id,
        "customer_name": req.customer_name.strip(),
        "customer_email": req.customer_email.strip(),
        "customer_tier": req.customer_tier.strip() if req.customer_tier else "Standard Retail",
        "intent": intent,
        "sentiment": sentiment,
        "subject": req.subject.strip(),
        "query": req.query.strip(),
        "priority": req.priority.title() if req.priority else "Medium",
        "status": "Open",
        "created_at": time.strftime("%b %d, %H:%M"),
        "created_ts": now_ts,
        "assigned_agent": "Unassigned",
        "transcript_snippet": req.transcript_snippet.strip() if req.transcript_snippet else req.query[:120],
        "messages": initial_messages
    }
    TICKETS_DB.insert(0, new_ticket)
    
    # Phase 7: Trigger Outbound Incident Webhook for Urgent or VIP Escalations
    if new_ticket["priority"] == "Urgent" or "VIP" in new_ticket["customer_tier"]:
        dispatch_webhook_alert(
            event_type="urgent_ticket_escalated",
            title=f"🚨 Urgent Escalation: Ticket #{ticket_id} ({new_ticket['customer_name']})",
            payload={"ticket_id": ticket_id, "customer_name": new_ticket["customer_name"], "priority": new_ticket["priority"], "tier": new_ticket["customer_tier"], "subject": new_ticket["subject"]},
            severity="high",
            destination="Slack #support-tier2-urgent"
        )
    
    returned_ticket = dict(new_ticket)
    returned_ticket["sla_details"] = calculate_sla_details(new_ticket)
    
    return {
        "status": "success",
        "message": f"Support Ticket {ticket_id} created successfully",
        "ticket": returned_ticket
    }

@app.get("/api/tickets/export")
def export_tickets(format: str = Query("csv", description="csv or json")):
    if format.lower() == "json":
        json_str = json.dumps(TICKETS_DB, indent=2)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="omnidesk_tickets_export.json"'}
        )
    
    # Default CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ticket ID", "Customer ID", "Customer Name", "Customer Email", 
        "Customer Tier", "Priority", "Status", "Intent", "Sentiment", 
        "Assigned Agent", "Created At", "Subject", "Query Context"
    ])
    
    for t in TICKETS_DB:
        writer.writerow([
            t.get("id", ""),
            t.get("customer_id", ""),
            t.get("customer_name", ""),
            t.get("customer_email", ""),
            t.get("customer_tier", ""),
            t.get("priority", ""),
            t.get("status", ""),
            t.get("intent", "General Inquiry"),
            t.get("sentiment", "Standard"),
            t.get("assigned_agent", "Unassigned"),
            t.get("created_at", ""),
            t.get("subject", ""),
            t.get("query", "")
        ])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="omnidesk_tickets_export.csv"'}
    )

@app.get("/api/kb/export")
def export_knowledge_base():
    chunks = get_all_chunks()
    json_str = json.dumps({
        "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_chunks": len(chunks),
        "chunks": chunks
    }, indent=2)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="omnidesk_kb_backup.json"'}
    )

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
            t_copy = dict(t)
            t_copy["sla_details"] = calculate_sla_details(t)
            return {
                "status": "success",
                "ticket": t_copy,
                **t_copy
            }
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

@app.post("/api/tickets/{ticket_id}/suggest-reply")
def suggest_agent_reply(ticket_id: str):
    for t in TICKETS_DB:
        if t["id"].upper() == ticket_id.upper():
            copilot_res = generate_agent_reply_draft(
                ticket_query=t.get("query", ""),
                customer_name=t.get("customer_name", "Valued Customer"),
                customer_tier=t.get("customer_tier", "Standard Retail"),
                intent=t.get("intent", "General Inquiry")
            )
            return {
                "ticket_id": t["id"],
                "customer_name": t.get("customer_name"),
                "customer_tier": t.get("customer_tier"),
                "intent": t.get("intent"),
                "suggested_reply": copilot_res["suggested_reply"],
                "sources": copilot_res["sources"],
                "latency_ms": copilot_res["latency_ms"]
            }
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

@app.post("/api/tickets/{ticket_id}/messages")
def add_ticket_message(ticket_id: str, req: TicketMessageRequest):
    for t in TICKETS_DB:
        if t["id"].upper() == ticket_id.upper():
            if "messages" not in t:
                t["messages"] = []
            new_msg = {
                "id": f"msg_{len(t['messages']) + 1}",
                "sender": req.sender.strip(),
                "text": req.text.strip(),
                "is_internal_note": bool(req.is_internal_note),
                "timestamp": time.strftime("%b %d, %H:%M")
            }
            t["messages"].append(new_msg)
            if not req.is_internal_note and t["status"] == "Open":
                t["status"] = "In Progress"
            
            t_copy = dict(t)
            t_copy["sla_details"] = calculate_sla_details(t)
            return {
                "status": "success",
                "message": "Message appended to ticket thread",
                "ticket_message": new_msg,
                "ticket": t_copy
            }
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
            t_copy = dict(t)
            t_copy["sla_details"] = calculate_sla_details(t)
            return {
                "status": "success",
                "message": f"Ticket {ticket_id} updated",
                "ticket": t_copy
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

@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    fb_entry = {
        "id": f"fb_{len(FEEDBACK_DB) + 1}",
        "query": req.query[:100] if req.query else "Live Assistant Query",
        "rating": req.rating,
        "is_positive": req.is_positive,
        "comment": req.comment.strip() if req.comment else "",
        "language": req.language or "English",
        "timestamp": time.strftime("%H:%M:%S")
    }
    FEEDBACK_DB.insert(0, fb_entry)
    if len(FEEDBACK_DB) > 50:
        FEEDBACK_DB.pop()
        
    # Phase 7: Trigger Outbound Webhook on Low CSAT rating
    if req.rating <= 2 or not req.is_positive:
        dispatch_webhook_alert(
            event_type="low_csat_alert",
            title=f"⚠️ Low CSAT Rating Received ({req.rating}/5.0)",
            payload={"rating": req.rating, "comment": req.comment, "query": req.query, "language": req.language},
            severity="medium",
            destination="Slack #csat-telemetry"
        )
        
    return {
        "status": "success",
        "message": "Thank you for your feedback!",
        "feedback": fb_entry
    }

class TestWebhookRequest(BaseModel):
    event_type: Optional[str] = "test_ping"
    channel: Optional[str] = "Slack #support-alerts"
    message: Optional[str] = "Simulated webhook delivery from OmniDesk AI Support Hub."

class BenchmarkRequest(BaseModel):
    num_queries: Optional[int] = 8

@app.post("/api/webhooks/test")
def trigger_test_webhook(req: TestWebhookRequest = None):
    ev_type = req.event_type if req and req.event_type else "test_ping"
    dest = req.channel if req and req.channel else "Slack #support-alerts"
    msg = req.message if req and req.message else "Simulated webhook delivery from OmniDesk AI Support Hub."
    
    entry = dispatch_webhook_alert(
        event_type=ev_type,
        title="🔔 Test Webhook Incident Dispatch",
        payload={"message": msg, "status": "Simulated Delivery Successful"},
        severity="info",
        destination=dest
    )
    return {
        "status": "success",
        "message": "Test webhook alert dispatched successfully",
        "webhook_log": entry
    }

@app.get("/api/webhooks/logs")
def get_webhook_logs():
    return {
        "total": len(WEBHOOK_LOGS_DB),
        "logs": WEBHOOK_LOGS_DB
    }

@app.post("/api/benchmark/simulate")
def run_benchmark_simulation(req: BenchmarkRequest = None):
    num_q = req.num_queries if req and req.num_queries else 8
    bench_data = run_synthetic_benchmark(num_queries=num_q)
    return bench_data

@app.get("/api/macros")
def list_macros():
    return {
        "total": len(MACROS_DB),
        "macros": MACROS_DB
    }

@app.post("/api/tickets/{ticket_id}/apply-macro")
def apply_ticket_macro(ticket_id: str, req: ApplyMacroRequest):
    selected_macro = next((m for m in MACROS_DB if m["id"] == req.macro_id), None)
    if not selected_macro:
        raise HTTPException(status_code=404, detail=f"Macro {req.macro_id} not found")
        
    for t in TICKETS_DB:
        if t["id"].upper() == ticket_id.upper():
            cust_name = t.get("customer_name", "Valued Customer")
            agent = t.get("assigned_agent", req.sender or "OmniDesk Support")
            if agent == "Unassigned":
                agent = req.sender or "OmniDesk Support"
                
            resolved_text = selected_macro["template"]
            resolved_text = resolved_text.replace("{{customer_name}}", cust_name)
            resolved_text = resolved_text.replace("{{ticket_id}}", t["id"])
            resolved_text = resolved_text.replace("{{assigned_agent}}", agent)
            
            new_msg = {
                "id": f"msg_{len(t.get('messages', [])) + 1}",
                "sender": agent,
                "text": resolved_text,
                "is_internal_note": False,
                "timestamp": time.strftime("%b %d, %H:%M")
            }
            if "messages" not in t:
                t["messages"] = []
            t["messages"].append(new_msg)
            t["status"] = "In Progress"
            
            t_copy = dict(t)
            t_copy["sla_details"] = calculate_sla_details(t)
            return {
                "status": "success",
                "message": f"Macro '{selected_macro['title']}' applied to ticket",
                "applied_text": resolved_text,
                "ticket": t_copy
            }
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

@app.get("/api/analytics")
def get_analytics():
    total_q = QUERY_STATS["total_queries"]
    deflected_q = QUERY_STATS["deflected_queries"]
    avg_latency = round((QUERY_STATS["total_latency_ms"] / total_q) / 1000, 2) if total_q > 0 else 0.42
    rate = round((deflected_q / total_q) * 100, 1) if total_q > 0 else 88.4

    # Compute live CSAT from feedback database
    if FEEDBACK_DB:
        csat_avg = round(sum(f["rating"] for f in FEEDBACK_DB) / len(FEEDBACK_DB), 2)
        pos_count = sum(1 for f in FEEDBACK_DB if f["is_positive"] or f["rating"] >= 4)
        pos_pct = round((pos_count / len(FEEDBACK_DB)) * 100, 1)
    else:
        csat_avg = 4.92
        pos_pct = 98.4

    return {
        "deflection_rate": rate,
        "avg_latency_s": avg_latency,
        "total_inquiries": total_q,
        "csat_score": csat_avg,
        "csat_positive_percent": pos_pct,
        "total_feedbacks": len(FEEDBACK_DB),
        "feedback_count": len(FEEDBACK_DB),
        "recent_feedback": FEEDBACK_DB[:5],
        "recent_webhooks": WEBHOOK_LOGS_DB[:5],
        "audit_logs": AUDIT_LOGS[:10]
    }

# ==============================================================================
# PHASE 8: HYBRID SEARCH & MULTI-MODAL VISION ENDPOINTS
# ==============================================================================

class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Search query string")
    top_k: Optional[int] = Field(3, ge=1, le=20)
    rrf_k: Optional[int] = Field(60, ge=1, le=200)

class VisionClaimRequest(BaseModel):
    image_base64: Optional[str] = Field("", description="Base64-encoded image string")
    claim_description: str = Field(..., min_length=1, max_length=2000, description="Customer claim explanation")
    mime_type: Optional[str] = Field("image/jpeg", max_length=50)

@app.post("/api/search/hybrid", dependencies=[Depends(check_rate_limit)])
def hybrid_search(req: HybridSearchRequest):
    try:
        return hybrid_search_rag(query=req.query.strip(), top_k=req.top_k, rrf_k=req.rrf_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vision/analyze-claim", dependencies=[Depends(check_rate_limit)])
def analyze_claim(req: VisionClaimRequest):
    try:
        return analyze_claim_image(
            image_base64=req.image_base64 or "",
            claim_description=req.claim_description.strip(),
            mime_type=req.mime_type or "image/jpeg"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    elif os.path.exists("app.html"):
        return FileResponse("app.html")
    return {"status": "online", "message": "OmniDesk Customer Support RAG Agent API is live. Visit /health or /docs."}

# Mount static asset folders
if os.path.exists("css"):
    app.mount("/css", StaticFiles(directory="css"), name="css")
if os.path.exists("js"):
    app.mount("/js", StaticFiles(directory="js"), name="js")

# Mount root static files if available
if os.path.exists("."):
    try:
        app.mount("/static", StaticFiles(directory=".", html=True), name="static")
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("BACKEND_PORT", "8000")))
    uvicorn.run(app, host=host, port=port)