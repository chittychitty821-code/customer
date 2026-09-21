"""
OmniDesk AI — Phase 8 Automated Test Suite
Validates:
1. Hybrid Search (BM25 + Vector RRF)
2. Multi-Modal Vision RAG Claim Inspection
"""

import os
import sys
import time
import base64
import requests

BASE_URL = os.environ.get("OMNIDESK_BACKEND_URL", "http://127.0.0.1:8000")

def log(step: str, detail: str = "", status: str = "PASS"):
    symbol = "🟢" if status == "PASS" else ("🔴" if status == "FAIL" else "ℹ️")
    print(f"[{symbol}] [Phase 8] {step}: {detail}")

def test_hybrid_search():
    """Validates BM25 + Dense Vector Reciprocal Rank Fusion."""
    res = requests.post(
        f"{BASE_URL}/api/search/hybrid",
        json={"query": "30-day return policy for electronics", "top_k": 3},
        timeout=15
    )
    assert res.status_code == 200, f"Hybrid search failed: {res.text}"
    data = res.json()
    assert data.get("status") == "success"
    results = data.get("fused_results", [])
    assert len(results) > 0
    assert "rrf_score" in results[0]
    log("Hybrid Search RRF", f"Retrieved {len(results)} fused clauses (Top RRF: {results[0]['rrf_score']})", "PASS")

def test_vision_claim_analysis():
    """Validates Multi-Modal Vision claim inspection with warranty policy grounding."""
    # 1. Test accidental drop damage claim
    drop_res = requests.post(
        f"{BASE_URL}/api/vision/analyze-claim",
        json={
            "claim_description": "Dropped phone on concrete, screen is shattered with cracks.",
            "image_base64": ""
        },
        timeout=15
    )
    assert drop_res.status_code == 200, f"Vision claim failed: {drop_res.text}"
    drop_data = drop_res.json()
    assert drop_data.get("status") == "success"
    assert drop_data.get("is_warranty_covered") is False
    assert "Section 4" in drop_data.get("grounded_policy_clause", "")
    log("Vision Claim (Drop Damage)", f"Verdict: {drop_data['claim_verdict']} (Grounded in {drop_data['grounded_policy_clause']})", "PASS")

    # 2. Test manufacturing defect claim
    defect_res = requests.post(
        f"{BASE_URL}/api/vision/analyze-claim",
        json={
            "claim_description": "Display panel has dead pixels and screen flicker after 2 months of normal use.",
            "image_base64": ""
        },
        timeout=15
    )
    assert defect_res.status_code == 200
    defect_data = defect_res.json()
    assert defect_data.get("status") == "success"
    assert defect_data.get("is_warranty_covered") is True
    log("Vision Claim (Manufacturer Defect)", f"Verdict: {defect_data['claim_verdict']}", "PASS")

def run_phase8_suite():
    print("\n" + "=" * 70)
    print("🔬 OMNIDESK AI — PHASE 8 FEATURE VALIDATION SUITE")
    print("=" * 70 + "\n")
    try:
        test_hybrid_search()
        test_vision_claim_analysis()
        print("\n" + "=" * 70)
        print("🎉 PHASE 8 VALIDATION SUCCESSFUL — ALL ENHANCEMENTS OPERATIONAL")
        print("=" * 70 + "\n")
        return 0
    except AssertionError as e:
        print(f"\n❌ PHASE 8 SUITE ASSERTION FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ PHASE 8 SUITE UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_phase8_suite())
