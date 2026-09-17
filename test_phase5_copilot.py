import os
import json
import time
from fastapi.testclient import TestClient
from server import app, TICKETS_DB

client = TestClient(app)

def test_sla_calculation_enrichment():
    res = client.get("/api/tickets")
    assert res.status_code == 200
    data = res.json()
    assert "tickets" in data
    assert len(data["tickets"]) >= 3
    for ticket in data["tickets"]:
        assert "sla_details" in ticket
        sla = ticket["sla_details"]
        assert "sla_target_minutes" in sla
        assert "remaining_minutes" in sla
        assert "badge_status" in sla
        assert "label" in sla
        assert sla["badge_status"] in ["urgent", "warning", "normal", "resolved", "breached"]

def test_suggest_agent_reply_endpoint():
    res = client.post("/api/tickets/TCK-1042/suggest-reply")
    assert res.status_code == 200
    data = res.json()
    assert data["ticket_id"] == "TCK-1042"
    assert "suggested_reply" in data
    assert len(data["suggested_reply"]) > 20
    assert "OmniDesk" in data["suggested_reply"] or "Elena" in data["suggested_reply"]
    assert "sources" in data

def test_ticket_message_threading():
    # Append regular message from agent
    post_res = client.post(
        "/api/tickets/TCK-1042/messages",
        json={
            "sender": "Agent Support",
            "text": "Hello Elena, we can provide 15% tier discount for 250 units.",
            "is_internal_note": False
        }
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "success"
    assert post_data["ticket_message"]["sender"] == "Agent Support"
    assert post_data["ticket_message"]["is_internal_note"] is False
    
    # Append internal note
    note_res = client.post(
        "/api/tickets/TCK-1042/messages",
        json={
            "sender": "Supervisor Mark",
            "text": "Approved discount with commercial sales director.",
            "is_internal_note": True
        }
    )
    assert note_res.status_code == 200
    note_data = note_res.json()
    assert note_data["ticket_message"]["is_internal_note"] is True

    # Verify messages in GET /api/tickets/TCK-1042
    get_res = client.get("/api/tickets/TCK-1042")
    assert get_res.status_code == 200
    t_data = get_res.json()
    assert len(t_data["messages"]) >= 3
    assert t_data["messages"][-1]["text"] == "Approved discount with commercial sales director."

def test_create_ticket_with_sla_and_initial_message():
    new_payload = {
        "customer_name": "Dr. Aris Thorne",
        "customer_email": "thorne@biolab.org",
        "customer_tier": "VIP Enterprise",
        "subject": "Expedited bio-cooler replacement",
        "query": "Our refrigeration cooler arrived damaged. We need express dispatch within 24 hours.",
        "priority": "Urgent",
        "intent": "Warranty & Claims"
    }
    res = client.post("/api/tickets", json=new_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    ticket = data["ticket"]
    assert ticket["priority"] == "Urgent"
    assert "sla_details" in ticket
    assert ticket["sla_details"]["sla_target_minutes"] == 60
    assert len(ticket["messages"]) == 1
    assert ticket["messages"][0]["text"] == new_payload["query"]

def run_phase5_tests():
    print("==================================================")
    print("RUNNING PHASE 5: AI COPILOT & SLA ENGINE TESTS")
    print("==================================================")
    
    print("\n[Test 1] Testing SLA calculation and countdown enrichment...")
    test_sla_calculation_enrichment()
    print(" PASS: Live SLA targets, remaining minutes, and status badges verified.")
    
    print("\n[Test 2] Testing Grounded AI Copilot reply suggestion...")
    test_suggest_agent_reply_endpoint()
    print(" PASS: AI Copilot draft generated with grounded store policy citations.")
    
    print("\n[Test 3] Testing Conversation Threading & Internal Staff Notes...")
    test_ticket_message_threading()
    print(" PASS: Customer replies and confidential internal notes logged.")
    
    print("\n[Test 4] Testing Ticket creation with initial thread & SLA...")
    test_create_ticket_with_sla_and_initial_message()
    print(" PASS: Initial inquiry threaded with urgent SLA target window.")
    
    print("\n==================================================")
    print("ALL PHASE 5 TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_phase5_tests()
