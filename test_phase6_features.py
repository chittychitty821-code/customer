"""
OmniDesk AI — Phase 6 Automated Test Suite
Validates:
1. Multi-Language Auto-Localization (Language Detection, Translation dictionaries & pipelines)
2. CSAT Feedback Telemetry & Dynamic Analytics Scoring
3. Macro Automation Rules Engine (Variable substitution: {{customer_name}}, {{ticket_id}}, {{assigned_agent}})
4. Multi-Language SSE Token Streaming
"""

import os
import sys
import json
import time
import requests

# Test against running server or fallback
BASE_URL = os.environ.get("OMNIDESK_BACKEND_URL", "http://127.0.0.1:8000")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "admin-secret-key-2026")

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": ADMIN_KEY
}

def log(step: str, detail: str = "", status: str = "INFO"):
    symbol = "🟢" if status == "PASS" else ("🔴" if status == "FAIL" else "ℹ️")
    print(f"[{symbol}] {step}: {detail}")

def test_language_detection_unit():
    """Unit test language detection in rag_engine."""
    from rag_engine import detect_language
    
    samples = {
        "What is the return policy?": "English",
        "¿Cuál es la política de devoluciones y reembolsos?": "Spanish",
        "Quelle est votre politique de retour et remboursement?": "French",
        "Wie lautet das Rückgaberecht für Einkäufe?": "German",
        "返品ポリシーと返金条件は何ですか？": "Japanese",
        "Qual é a política de devolução e reembolso?": "Portuguese",
        "वापसी और धनवापसी नीति क्या है?": "Hindi",
    }
    
    for text, expected in samples.items():
        detected = detect_language(text)
        assert detected == expected, f"Expected {expected}, got {detected} for '{text}'"
        log("Language Detection", f"'{text[:30]}...' -> {detected}", "PASS")
    
    log("Unit: Language Detection", "All 7 languages accurately classified", "PASS")

def test_multilingual_rag_query():
    """Verify localized RAG answering via backend /ask endpoint."""
    queries = [
        ("¿Cuál es la política de devoluciones?", "Spanish", ["30", "días", "devoluc"]),
        ("Quelle est la politique de retour?", "French", ["30", "jours", "retour"]),
        ("Was ist das Rückgaberecht?", "German", ["30", "Tage", "Rückgabe"]),
    ]
    
    for query_text, expected_lang, keywords in queries:
        payload = {"query": query_text, "language": expected_lang}
        res = requests.post(f"{BASE_URL}/ask", json=payload, timeout=10)
        assert res.status_code == 200, f"Error {res.status_code}: {res.text}"
        data = res.json()
        
        assert data.get("language") == expected_lang, f"Expected lang {expected_lang}, got {data.get('language')}"
        answer = data.get("answer", "").lower()
        
        matched_kw = [kw for kw in keywords if kw.lower() in answer]
        assert len(matched_kw) > 0, f"Answer missing expected keywords {keywords}. Got: {answer}"
        log(f"Multi-Lang RAG ({expected_lang})", f"Answer localized with keywords: {matched_kw}", "PASS")

def test_csat_feedback_and_analytics():
    """Verify customer satisfaction feedback logging and dynamic score aggregation."""
    # 1. Post a positive rating
    pos_res = requests.post(
        f"{BASE_URL}/api/feedback",
        json={
            "is_positive": True,
            "rating": 5,
            "comment": "Super fast and accurate Spanish response!",
            "query": "¿Cuál es la política de devoluciones?",
            "response": "Nuestra política de devolución estándar es de 30 días...",
            "language": "Spanish"
        },
        timeout=5
    )
    assert pos_res.status_code == 200, f"Failed positive feedback: {pos_res.text}"
    pos_data = pos_res.json()
    assert pos_data.get("status") == "success"
    log("CSAT Feedback", f"Positive rating logged (ID: {pos_data.get('feedback', {}).get('id')})", "PASS")
    
    # 2. Post a negative rating
    neg_res = requests.post(
        f"{BASE_URL}/api/feedback",
        json={
            "is_positive": False,
            "rating": 2,
            "comment": "Needs more details on courier pickup.",
            "query": "How to ship heavy electronics?",
            "response": "Please consult shipping policies.",
            "language": "English"
        },
        timeout=5
    )
    assert neg_res.status_code == 200, f"Failed negative feedback: {neg_res.text}"
    log("CSAT Feedback", "Negative rating logged successfully", "PASS")
    
    # 3. Check Analytics Dynamic CSAT Score
    an_res = requests.get(f"{BASE_URL}/api/analytics", headers=HEADERS, timeout=5)
    assert an_res.status_code == 200, f"Failed to get analytics: {an_res.text}"
    an_data = an_res.json()
    
    assert "csat_score" in an_data, "Missing csat_score in analytics"
    assert "csat_positive_percent" in an_data, "Missing csat_positive_percent in analytics"
    assert "feedback_count" in an_data, "Missing feedback_count in analytics"
    
    csat = an_data["csat_score"]
    pos_pct = an_data["csat_positive_percent"]
    fb_count = an_data["feedback_count"]
    
    assert 1.0 <= csat <= 5.0, f"Invalid CSAT score: {csat}"
    assert 0.0 <= pos_pct <= 100.0, f"Invalid CSAT positive %: {pos_pct}"
    assert fb_count >= 2, f"Feedback count should be >= 2, got {fb_count}"
    
    log("Dynamic CSAT Analytics", f"CSAT: {csat}/5.0 | Positive: {pos_pct}% | Total Feedback: {fb_count}", "PASS")

def test_macro_rules_and_variable_substitution():
    """Verify macro template retrieval, variable injection, and ticket message posting."""
    # 1. Fetch available macros
    m_res = requests.get(f"{BASE_URL}/api/macros", timeout=5)
    assert m_res.status_code == 200, f"Failed to get macros: {m_res.text}"
    macros = m_res.json().get("macros", [])
    assert len(macros) >= 4, f"Expected at least 4 macros, got {len(macros)}"
    
    macro_ids = [m["id"] for m in macros]
    assert "macro_return_rma" in macro_ids
    assert "macro_warranty_claim" in macro_ids
    assert "macro_price_match" in macro_ids
    assert "macro_intl_ddp" in macro_ids
    log("Macro Catalog", f"Retrieved {len(macros)} automation rules ({', '.join(macro_ids)})", "PASS")
    
    # 2. Create a test ticket
    t_res = requests.post(
        f"{BASE_URL}/api/tickets",
        json={
            "customer_name": "Marcus Vance",
            "customer_email": "marcus.vance@techcorp.io",
            "priority": "High",
            "subject": "Requesting 30-Day Return Authorization",
            "query": "I received my order yesterday but need to initiate a return for store credit."
        },
        timeout=5
    )
    assert t_res.status_code == 200, f"Failed to create test ticket: {t_res.text}"
    t_data = t_res.json().get("ticket", {})
    ticket_id = t_data["id"]
    customer_name = t_data["customer_name"]
    log("Ticket Created", f"Ticket {ticket_id} created for {customer_name}", "PASS")
    
    # 3. Apply macro_return_rma to ticket
    app_res = requests.post(
        f"{BASE_URL}/api/tickets/{ticket_id}/apply-macro",
        json={"macro_id": "macro_return_rma"},
        timeout=5
    )
    assert app_res.status_code == 200, f"Failed to apply macro: {app_res.text}"
    app_data = app_res.json()
    applied_text = app_data.get("applied_text", "")
    
    # Verify variable substitution
    assert customer_name in applied_text, f"Expected customer name '{customer_name}' in applied macro, got: {applied_text}"
    assert ticket_id in applied_text, f"Expected ticket ID '{ticket_id}' in applied macro, got: {applied_text}"
    assert "{{customer_name}}" not in applied_text, "Unresolved placeholder {{customer_name}}"
    assert "{{ticket_id}}" not in applied_text, "Unresolved placeholder {{ticket_id}}"
    
    log("Macro Variable Substitution", f"Template successfully populated:\n---\n{applied_text[:120]}...\n---", "PASS")
    
    # 4. Verify message logged in ticket thread
    get_t = requests.get(f"{BASE_URL}/api/tickets/{ticket_id}", timeout=5)
    assert get_t.status_code == 200
    res_obj = get_t.json()
    messages = res_obj.get("ticket", {}).get("messages", []) or res_obj.get("messages", [])
    assert len(messages) >= 2, f"Macro was not posted to ticket conversation thread. Total: {len(messages)}"
    assert messages[-1]["text"] == applied_text
    log("Ticket Conversation Thread", f"Macro message verified in thread (Total msgs: {len(messages)})", "PASS")

def test_sse_streaming_multilingual():
    """Verify multilingual SSE token streaming via /ask/stream."""
    url = f"{BASE_URL}/ask/stream"
    payload = {"query": "What is your return policy?", "language": "Spanish"}
    
    res = requests.post(url, json=payload, stream=True, timeout=10)
    assert res.status_code == 200, f"Streaming failed: {res.status_code}"
    
    events_received = []
    text_chunks = []
    current_event = None
    
    for line in res.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("event: "):
                current_event = decoded[7:].strip()
                events_received.append(current_event)
            elif decoded.startswith("data: ") and current_event:
                data_obj = json.loads(decoded[6:])
                if current_event == "token":
                    text_chunks.append(data_obj.get("token", ""))
    
    assert "sources" in events_received, f"Missing sources event in SSE stream: {events_received}"
    assert "token" in events_received, f"Missing token events in SSE stream: {events_received}"
    assert "done" in events_received, f"Missing done event in SSE stream: {events_received}"
    
    full_stream_text = "".join(text_chunks)
    assert len(full_stream_text) > 20, f"Streamed text too short: {full_stream_text}"
    log("Multi-Lang SSE Streaming", f"Received {len(text_chunks)} tokens. Streamed: '{full_stream_text[:60]}...'", "PASS")

def run_all_tests():
    print("\n=======================================================")
    print("🚀 OMNIDESK AI — PHASE 6 AUTOMATED TEST RUNNER")
    print("=======================================================\n")
    
    try:
        test_language_detection_unit()
        test_multilingual_rag_query()
        test_csat_feedback_and_analytics()
        test_macro_rules_and_variable_substitution()
        test_sse_streaming_multilingual()
        
        print("\n=======================================================")
        print("🎉 ALL PHASE 6 AUTOMATED TESTS PASSED SUCCESSFULLY! (5/5)")
        print("=======================================================\n")
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST ASSERTION FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
