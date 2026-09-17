import os
import json
import csv
import io
from fastapi.testclient import TestClient

import server
from server import app
from rag_engine import classify_intent_and_sentiment

def run_phase4_tests():
    print("==================================================")
    print("RUNNING PHASE 4: MULTI-CHANNEL & INTENT TESTS")
    print("==================================================")
    
    client = TestClient(app)

    # 1. Test Intent and Sentiment Classification Logic
    print("\n[Test 1] Testing Intent & Sentiment Classification Engine...")
    
    t1 = classify_intent_and_sentiment("Can I return open-box headphones for a full refund within 30 days?")
    assert t1["intent"] == "Return & Refund", f"Expected Return & Refund, got {t1['intent']}"
    print(f" PASS: Return query correctly classified: {t1}")

    t2 = classify_intent_and_sentiment("Do you offer express shipping to Canada via DHL with DDP duties?")
    assert t2["intent"] == "Shipping & Logistics", f"Expected Shipping & Logistics, got {t2['intent']}"
    print(f" PASS: Shipping query correctly classified: {t2}")

    t3 = classify_intent_and_sentiment("My product arrived completely broken and defective! This is urgent!")
    assert t3["intent"] == "Warranty & Claims", f"Expected Warranty & Claims, got {t3['intent']}"
    assert t3["sentiment"] == "High Urgency", f"Expected High Urgency, got {t3['sentiment']}"
    print(f" PASS: Warranty claim with high urgency classified: {t3}")

    t4 = classify_intent_and_sentiment("We require corporate volume discount pricing for 200 enterprise licenses.")
    assert t4["intent"] == "Billing & Payment", f"Expected Billing & Payment, got {t4['intent']}"
    assert t4["sentiment"] == "VIP / Commercial", f"Expected VIP / Commercial, got {t4['sentiment']}"
    print(f" PASS: Enterprise B2B inquiry classified: {t4}")

    # 2. Test Automated Ticket Creation with Intent & Sentiment Tagging
    print("\n[Test 2] Testing Ticket Creation with Automatic Intent Tagging...")
    create_res = client.post("/api/tickets", json={
        "customer_name": "Liam Gallagher",
        "customer_email": "liam@oasis-audio.co.uk",
        "subject": "Overnight delivery to Manchester UK",
        "query": "Can I arrange guaranteed overnight Saturday delivery for 10 units?",
        "priority": "High"
    })
    assert create_res.status_code == 200, f"Expected 200, got {create_res.status_code}"
    created_ticket = create_res.json()["ticket"]
    assert "id" in created_ticket
    assert created_ticket["intent"] == "Shipping & Logistics"
    assert created_ticket["customer_id"].startswith("CUST-")
    print(f" PASS: Ticket created with ID {created_ticket['id']}, Cust ID {created_ticket['customer_id']}, Intent: {created_ticket['intent']}")

    # 3. Test CSV Ticket Export
    print("\n[Test 3] Testing CRM CSV Ticket Export...")
    csv_res = client.get("/api/tickets/export?format=csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "attachment" in csv_res.headers.get("content-disposition", "")
    
    csv_reader = csv.reader(io.StringIO(csv_res.text))
    header = next(csv_reader)
    assert "Ticket ID" in header
    assert "Customer ID" in header
    assert "Intent" in header
    assert "Sentiment" in header
    rows = list(csv_reader)
    assert len(rows) >= 3
    print(f" PASS: Valid CSV export generated with {len(rows)} tickets and columns: {header[:6]}")

    # 4. Test JSON Ticket Export
    print("\n[Test 4] Testing JSON Dataset Export...")
    json_res = client.get("/api/tickets/export?format=json")
    assert json_res.status_code == 200
    data = json_res.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    print(f" PASS: JSON export generated with {len(data)} ticket records.")

    # 5. Test Knowledge Base Vector Backup Export
    print("\n[Test 5] Testing Knowledge Base JSON Backup...")
    kb_res = client.get("/api/kb/export")
    assert kb_res.status_code == 200
    kb_data = kb_res.json()
    assert "total_chunks" in kb_data
    assert "chunks" in kb_data
    assert kb_data["total_chunks"] >= 5
    print(f" PASS: KB Backup generated with {kb_data['total_chunks']} chunks.")

    print("\n==================================================")
    print("ALL PHASE 4 TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_phase4_tests()
