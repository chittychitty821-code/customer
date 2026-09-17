import os
import time
from fastapi.testclient import TestClient

# Set up test environment variables
os.environ["RATE_LIMIT_PER_MINUTE"] = "10"  # Small rate limit for testing
os.environ["ADMIN_API_KEY"] = "super-secret-test-key-123"

# Re-import server with test configuration
import server
from server import app, rate_limiter

# Explicitly ensure test config is active regardless of module import order
server.ADMIN_API_KEY = "super-secret-test-key-123"
server.RATE_LIMIT_PER_MINUTE = 10
server.rate_limiter.limit = 10

def run_hardening_tests():
    print("==================================================")
    print("RUNNING PHASE 2 PRODUCTION HARDENING TESTS")
    print("==================================================")
    
    client = TestClient(app)
    
    # 1. Test Input Payload Validation (Pydantic max_length & empty checks)
    print("\n[Test 1] Testing Payload Length Validation...")
    
    # Empty query check
    empty_res = client.post("/ask", json={"query": ""})
    assert empty_res.status_code == 422, f"Expected 422 for empty query, got {empty_res.status_code}"
    print(" PASS: Empty query correctly rejected with 422 Unprocessable Entity.")

    # Oversized query (>2000 characters)
    huge_query = "What is your policy? " * 150  # ~3,150 chars
    huge_res = client.post("/ask", json={"query": huge_query})
    assert huge_res.status_code == 422, f"Expected 422 for oversized query, got {huge_res.status_code}"
    print(" PASS: Oversized query (>2000 chars) correctly rejected with 422.")

    # 2. Test Admin API Key Protection
    print("\n[Test 2] Testing Admin API Key Authorization...")
    
    # Attempt to add chunk without key -> Should be 401 Unauthorized
    unauth_res = client.post("/api/kb/add", json={
        "title": "Unauthorized Section",
        "content": "This should not be allowed without admin key."
    })
    assert unauth_res.status_code == 401, f"Expected 401 Unauthorized without API key, got {unauth_res.status_code}"
    print(" PASS: Unauthenticated KB addition rejected with 401.")

    # Attempt to add chunk with wrong key -> Should be 401
    wrong_key_res = client.post("/api/kb/add", 
        headers={"X-API-Key": "wrong-key-456"},
        json={"title": "Unauthorized Section", "content": "Wrong key content."}
    )
    assert wrong_key_res.status_code == 401, f"Expected 401 with wrong key, got {wrong_key_res.status_code}"
    print(" PASS: Incorrect API key rejected with 401.")

    # Attempt to add chunk with valid key -> Should be 200 OK
    auth_res = client.post("/api/kb/add",
        headers={"X-API-Key": "super-secret-test-key-123"},
        json={
            "title": "Section 8: Hardened VIP Policy",
            "content": "VIP members receive priority 24/7 dedicated support and free lifetime returns.",
            "source": "vip_policy.txt"
        }
    )
    assert auth_res.status_code == 200, f"Expected 200 with valid admin key, got {auth_res.status_code}"
    cid = auth_res.json()["chunk"]["id"]
    print(f" PASS: Valid Admin API key accepted. Added chunk: {cid}")

    # Delete test chunk with valid key
    del_res = client.delete(f"/api/kb/chunks/{cid}", headers={"X-API-Key": "super-secret-test-key-123"})
    assert del_res.status_code == 200, f"Expected 200 on delete, got {del_res.status_code}"
    print(" PASS: Valid admin key permitted chunk deletion.")

    # 3. Test Sliding-Window Rate Limiting
    print("\n[Test 3] Testing Sliding-Window Rate Limiting...")
    rate_limiter.requests.clear()  # Reset rate limit tracker
    
    # Perform 10 requests within limit (limit is 10)
    for i in range(10):
        r = client.post("/ask", json={"query": f"Test question {i}"})
        assert r.status_code == 200, f"Request {i+1} failed unexpectedly: {r.status_code}"
    
    print(" PASS: 10 queries within rate limit succeeded with 200 OK.")

    # 11th request should trigger 429 Too Many Requests
    rate_limited_res = client.post("/ask", json={"query": "Burst question exceeding limit"})
    assert rate_limited_res.status_code == 429, f"Expected 429 Too Many Requests, got {rate_limited_res.status_code}"
    assert "Retry-After" in rate_limited_res.headers, "Retry-After header missing in 429 response"
    print(f" PASS: 11th request throttled with HTTP 429. Retry-After: {rate_limited_res.headers.get('Retry-After')}s")

    # 4. Test Health & Diagnostics
    print("\n[Test 4] Testing Health & Security Telemetry...")
    info_res = client.get("/api/info")
    assert info_res.status_code == 200, f"Expected 200 for /api/info, got {info_res.status_code}"
    info_data = info_res.json()
    assert info_data["admin_auth_enabled"] is True, "admin_auth_enabled should be True"
    assert info_data["rate_limit_per_min"] == 10, "rate_limit_per_min should be 10"
    print(f" PASS: Diagnostics confirmed: auth_enabled={info_data['admin_auth_enabled']}, rate_limit={info_data['rate_limit_per_min']}")

    print("\n==================================================")
    print("ALL PRODUCTION HARDENING TESTS PASSED! ")
    print("==================================================")

if __name__ == "__main__":
    run_hardening_tests()
