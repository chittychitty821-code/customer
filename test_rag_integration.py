import os
import sys
import json
from fastapi.testclient import TestClient

from server import app
from rag_engine import (
    ingest_faq,
    get_all_chunks,
    add_knowledge_chunk,
    delete_knowledge_chunk,
    run_rag_pipeline,
    stream_rag_pipeline,
    get_pipeline_settings,
    update_pipeline_settings,
    collection,
    DEFAULT_KB_PATH
)

def run_all_tests():
    print("==================================================")
    print("RUNNING OMNIDESK AI PHASE 1 INTEGRATION TESTS")
    print("==================================================")
    
    # 1. Test Ingestion & Vector Count
    print("\n[Test 1] Testing Knowledge Base Ingestion...")
    ingest_faq(DEFAULT_KB_PATH, force_reindex=False)
    chunks = get_all_chunks()
    assert len(chunks) > 0, f"Expected > 0 chunks, got {len(chunks)}"
    print(f" PASS: Vector store contains {len(chunks)} chunks.")

    # 2. Test Direct RAG Pipeline Non-Streaming
    print("\n[Test 2] Testing Grounded RAG Query ('What is the return policy?')...")
    res = run_rag_pipeline("What is your 30-day return policy for electronics?")
    assert "answer" in res and res["answer"], "Answer was empty"
    assert "sources" in res, "Sources field missing"
    assert res.get("deflected") is False, "Query was unexpectedly deflected"
    print(f" PASS: Answer received: {res['answer'][:80]}... (latency: {res['latency_ms']}ms)")

    # 3. Test Guardrail Deflection on Out-of-Scope Query
    print("\n[Test 3] Testing Guardrail Deflection ('Who won the 1994 World Cup?')...")
    guard_res = run_rag_pipeline("Who won the 1994 World Cup in football?")
    assert "answer" in guard_res, "Guardrail answer missing"
    print(f" PASS: Out-of-scope inquiry handled. Answer: {guard_res['answer'][:70]}...")

    # 4. Test Streaming Generator
    print("\n[Test 4] Testing SSE Stream Generator...")
    events = list(stream_rag_pipeline("Do you ship to Canada?"))
    assert len(events) > 0, "No events yielded by stream generator"
    has_sources_event = any("event: sources" in ev for ev in events)
    has_token_event = any("event: token" in ev for ev in events)
    has_done_event = any("event: done" in ev for ev in events)
    assert has_sources_event, "Stream missing sources event"
    assert has_token_event, "Stream missing token event"
    assert has_done_event, "Stream missing done event"
    print(f" PASS: Stream yielded {len(events)} SSE chunks with sources, tokens, and done events.")

    # 5. Test Dynamic KB Addition & Deletion
    print("\n[Test 5] Testing Dynamic Policy Clause Ingestion...")
    new_clause = add_knowledge_chunk(
        title="Section 7: Student Discount Program",
        content="Students with a valid .edu email address receive an additional 10% discount on all purchases using code STUDENT10.",
        source="student_policy.txt"
    )
    assert "id" in new_clause, "New clause ID missing"
    cid = new_clause["id"]
    print(f" Added new clause with ID: {cid}")
    
    # Query for the new policy
    new_query_res = run_rag_pipeline("Is there a student discount with .edu email?")
    assert "answer" in new_query_res, "Query for new clause failed"
    print(f" Query on newly added chunk: {new_query_res['answer'][:80]}...")
    
    # Delete the test chunk
    del_res = delete_knowledge_chunk(cid)
    assert del_res is True, "Failed to delete test chunk"
    print(" PASS: Dynamic clause successfully added, queried, and deleted.")

    # 6. Test FastAPI HTTP Endpoints via TestClient
    print("\n[Test 6] Testing FastAPI REST Endpoints...")
    client = TestClient(app)

    # /health
    h = client.get("/health")
    assert h.status_code == 200, f"Health check failed: {h.status_code}"
    print(f" /health: {h.json()}")

    # /api/info
    info = client.get("/api/info")
    assert info.status_code == 200, f"Info endpoint failed: {info.status_code}"
    print(f" /api/info: {info.json()['generation_model']}, {info.json()['document_chunks']} chunks")

    # /ask
    ask_res = client.post("/ask", json={"query": "What is the warranty coverage?"})
    assert ask_res.status_code == 200, f"/ask failed: {ask_res.status_code}"
    assert "answer" in ask_res.json(), "Answer missing in /ask"
    print(f" /ask: Answer received successfully")

    # /ask/stream
    stream_res = client.post("/ask/stream", json={"query": "What is the order cancellation window?"})
    assert stream_res.status_code == 200, f"/ask/stream failed: {stream_res.status_code}"
    assert "event: sources" in stream_res.text, "SSE text missing sources"
    print(f" /ask/stream: SSE stream validated")

    # /api/kb/chunks
    kb_list = client.get("/api/kb/chunks")
    assert kb_list.status_code == 200, f"KB list failed: {kb_list.status_code}"
    assert len(kb_list.json()["chunks"]) > 0, "No chunks returned"
    print(f" /api/kb/chunks: {len(kb_list.json()['chunks'])} chunks listed")

    # /api/settings
    update_res = client.post("/api/settings", json={"guardrail_threshold": 1.15, "top_k_chunks": 3})
    assert update_res.status_code == 200, f"Settings update failed: {update_res.status_code}"
    assert update_res.json()["settings"]["guardrail_threshold"] == 1.15, "Settings threshold mismatch"
    print(" /api/settings: runtime settings updated successfully")

    # /api/analytics
    analytics_res = client.get("/api/analytics")
    assert analytics_res.status_code == 200, f"Analytics failed: {analytics_res.status_code}"
    assert "deflection_rate" in analytics_res.json(), "Deflection rate missing"
    print(f" /api/analytics: Deflection rate {analytics_res.json()['deflection_rate']}%, CSAT: {analytics_res.json()['csat_score']}")

    print("\n==================================================")
    print("ALL PHASE 1 INTEGRATION TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_all_tests()
