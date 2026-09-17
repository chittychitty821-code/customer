import os
from fastapi.testclient import TestClient

os.environ["ADMIN_API_KEY"] = "admin-secret-escalation-key"

from server import app

def run_ticket_tests():
    print("==================================================")
    print("RUNNING PHASE 3 TICKET & ESCALATION TESTS")
    print("==================================================")

    client = TestClient(app)

    # 1. Test Ticket Creation
    print("\n[Test 1] Testing Automated Ticket Creation...")
    create_res = client.post("/api/tickets", json={
        "customer_name": "Samantha Reed",
        "customer_email": "s.reed@globalenterprise.com",
        "subject": "Custom B2B SLA Agreement Request",
        "query": "We require a custom 99.99% uptime SLA guarantee contract for our deployment.",
        "priority": "Urgent",
        "transcript_snippet": "Customer requested customized enterprise SLA guarantee."
    })
    assert create_res.status_code == 200, f"Ticket creation failed: {create_res.status_code}"
    ticket_data = create_res.json()["ticket"]
    ticket_id = ticket_data["id"]
    assert ticket_id.startswith("TCK-"), f"Invalid ticket ID format: {ticket_id}"
    assert ticket_data["priority"] == "Urgent", f"Priority mismatch: {ticket_data['priority']}"
    assert ticket_data["status"] == "Open", f"Status should be Open, got {ticket_data['status']}"
    print(f" PASS: Ticket created successfully: {ticket_id} ({ticket_data['subject']})")

    # 2. Test Listing & Status Filtering
    print("\n[Test 2] Testing Tickets Listing & Filtering...")
    all_res = client.get("/api/tickets")
    assert all_res.status_code == 200, f"List failed: {all_res.status_code}"
    total = all_res.json()["total"]
    assert total >= 1, "Expected at least 1 ticket"
    print(f" Total tickets in database: {total}")

    # Filter Open
    open_res = client.get("/api/tickets?status=Open")
    assert open_res.status_code == 200
    for t in open_res.json()["tickets"]:
        assert t["status"] == "Open", f"Expected status Open, got {t['status']}"
    print(f" PASS: Filter by Open status returned {open_res.json()['total']} tickets.")

    # 3. Test Ticket Status Transitions
    print(f"\n[Test 3] Testing Status Transitions for {ticket_id}...")
    
    # Transition to 'In Progress'
    in_prog_res = client.patch(f"/api/tickets/{ticket_id}", json={
        "status": "In Progress",
        "assigned_agent": "Alex Morgan"
    })
    assert in_prog_res.status_code == 200, f"Status update failed: {in_prog_res.status_code}"
    assert in_prog_res.json()["ticket"]["status"] == "In Progress"
    assert in_prog_res.json()["ticket"]["assigned_agent"] == "Alex Morgan"
    print(f" Updated {ticket_id} -> In Progress (Agent: Alex Morgan)")

    # Transition to 'Resolved'
    resolved_res = client.patch(f"/api/tickets/{ticket_id}", json={
        "status": "Resolved"
    })
    assert resolved_res.status_code == 200
    assert resolved_res.json()["ticket"]["status"] == "Resolved"
    print(f" PASS: Updated {ticket_id} -> Resolved")

    # 4. Test Ticket Metrics & Stats
    print("\n[Test 4] Testing Ticket Analytics & Resolution Rate...")
    stats_res = client.get("/api/tickets/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_tickets" in stats, "Total tickets metric missing"
    assert "resolution_rate_percent" in stats, "Resolution rate metric missing"
    print(f" PASS: Metrics: {stats['total_tickets']} total, {stats['open_tickets']} open, {stats['resolved_tickets']} resolved ({stats['resolution_rate_percent']}% rate)")

    # 5. Test Ticket Deletion with Admin Authorization
    print(f"\n[Test 5] Testing Ticket Deletion for {ticket_id}...")
    # Unauthorized delete should fail
    unauth_del = client.delete(f"/api/tickets/{ticket_id}")
    assert unauth_del.status_code == 401, f"Expected 401 for unauthorized delete, got {unauth_del.status_code}"
    
    # Authorized delete should succeed
    auth_del = client.delete(f"/api/tickets/{ticket_id}", headers={"X-API-Key": "admin-secret-escalation-key"})
    assert auth_del.status_code == 200, f"Expected 200 for authorized delete, got {auth_del.status_code}"
    print(f" PASS: Ticket {ticket_id} deleted successfully.")

    print("\n==================================================")
    print("ALL PHASE 3 TICKET & ESCALATION TESTS PASSED! ")
    print("==================================================")

if __name__ == "__main__":
    run_ticket_tests()
