# OmniDesk AI — Engineering & Operational Rules

---

## 1. Zero-Hallucination & AI Safety Rules

The primary design principle of OmniDesk AI is **absolute adherence to verified company documentation**. All AI inference pipelines must strictly obey the following contracts:

### Rule 1.1: The Grounded Context Contract

- The language model **must never** extrapolate, assume, or synthesize facts, policies, numbers, prices, or timelines that are not explicitly present in the provided `<context>` payload.
- System prompt instructions must unconditionally enforce:

  ```text
  "Rely ONLY on the facts explicitly mentioned in the provided <context>. 
   Do not extrapolate, assume, or fabricate any rules, dates, or prices. 
   If the answer is not explicitly written in the context, output:
   'I am sorry, but our documentation does not cover that. Please contact support@company.com.'"
  ```

### Rule 1.2: Deterministic Distance Guardrails

- Every vector query executes against ChromaDB with cosine distance metric ($0.0 \le \text{dist} \le 2.0$).
- If the nearest chunk distance exceeds `guardrail_threshold` (default: `1.2`), the system **must** immediately deflect the query.
- Deflected queries must return `deflected: true`, empty source citations, and offer an immediate escalation path to human support.

### Rule 1.3: Deterministic Offline Fallback Rule

- If the external Gemini API key is missing, invalid, rate-limited, or network-blocked, the RAG engine **must not crash**.
- It must seamlessly fall back to the deterministic local grounded answer generator (`generate_local_grounded_answer`) and hash-based L2-normalized embeddings (`_generate_deterministic_embedding`).

---

## 2. API & Backend Engineering Rules

### Rule 2.1: HTTP Status Code Standardization

The FastAPI backend must strictly adhere to the following REST conventions:

- `200 OK`: Successful query, list, or update operation.
- `400 Bad Request`: Missing or malformed query text.
- `401 Unauthorized`: Missing or invalid `X-API-Key` on protected management endpoints.
- `404 Not Found`: Target ticket ID or KB chunk ID does not exist.
- `422 Unprocessable Entity`: Pydantic validation error (e.g. empty string or query exceeding 2,000 characters).
- `429 Too Many Requests`: Client exceeded sliding-window rate limit (60 RPM). Must return `Retry-After` header.
- `500 Internal Server Error`: Unhandled server exception with descriptive JSON detail.

### Rule 2.2: Rate Limiting Enforcement

- All public inference endpoints (`/ask`, `/ask/stream`) must be wrapped with the `check_rate_limit` dependency.
- Rate limits are calculated on a rolling 60-second window per client IP.

### Rule 2.3: Admin Authorization Matrix

The following mutating endpoints **require** admin verification:

- `POST /api/kb/add`
- `DELETE /api/kb/chunks/{chunk_id}`
- `POST /api/kb/reset`
- `POST /api/settings`
- `DELETE /api/tickets/{ticket_id}`

Authorization must check `X-API-Key` first, then fall back to `Authorization: Bearer <key>`. If `ADMIN_API_KEY` is empty in environment variables, the system operates in open developer mode.

---

## 3. Frontend & State Management Rules

### Rule 3.1: Vanilla JavaScript & CSS Architecture

- All web applications in this repository must use **Vanilla JavaScript (ES6+)** and **Vanilla CSS** without heavy runtime frameworks (React/Vue/Tailwind) unless explicitly mandated.
- UI styling must follow the design token system in `css/style.css` (Glassmorphism, custom scrollbars, cyber-enterprise dark palette).

### Rule 3.2: SSE Streaming Protocol

- Real-time token streams from `/ask/stream` must follow the SSE event sequence:
  1. `event: sources` $\to$ Payload with matched documents, distances, and deflection state.
  2. `event: token` $\to$ Streamed individual text tokens.
  3. `event: done` $\to$ Final metadata payload with latency, intent, and language.

### Rule 3.3: Client-Side Resilience

- If the backend is offline, the SPA (`js/app.js`) must seamlessly switch to internal fallback mode, allowing offline testing of knowledge base chunks, mock tickets, and local grounded answers.
- User settings (backend URL, admin API key, guardrail threshold, language) must be persisted in `localStorage` with `omni_` prefixes.

---

## 4. Ticket Lifecycle & SLA Escalation Rules

### Rule 4.1: Automated Routing & Tier Assignment

- Every ticket created must be assigned an immutable `TCK-XXXX` identifier and a customer profile `CUST-XXXX`.
- Priority mappings:
  - `VIP Enterprise` $\to$ Default priority: `Urgent` or `High` (SLA: 1h to 4h).
  - `Pro Business` $\to$ Default priority: `High` or `Medium` (SLA: 4h to 24h).
  - `Standard Retail` $\to$ Default priority: `Medium` or `Low` (SLA: 24h to 48h).

### Rule 4.2: Confidential Internal Staff Notes

- Messages with `is_internal_note: true` must be styled with distinct amber borders (`🔒 Staff Note`) and hidden from customer-facing exports.
- Adding a staff note does not transition an `Open` ticket to `In Progress`; only customer-facing agent replies change status.

### Rule 4.3: Outbound Incident Webhooks

- Automated webhook incident dispatching (`dispatch_webhook_alert`) is triggered when:
  1. An `Urgent` priority ticket or `VIP Enterprise` ticket is created.
  2. A CSAT feedback rating $\le 2/5$ is submitted.
  3. A ticket's remaining SLA window falls below 30 minutes.

---

## 5. Testing & Verification Standards

### Rule 5.1: Master Test Suite Integrity

- No pull request or major feature commit may be merged without all 7 phases passing in `test_master_suite.py`.
- The test suite must output a clean 100% executive scorecard across all phases:
  - Phase 1: Core Grounded RAG & SSE Streaming
  - Phase 2: Production Hardening & Security
  - Phase 3: Escalation & Customer ID Routing
  - Phase 4: Intent Classification & CRM Export
  - Phase 5: AI Copilot & Conversation Threading
  - Phase 6: Multi-Language & Macro Automation
  - Phase 7: Webhooks Alerting & Synthetic Benchmarking
