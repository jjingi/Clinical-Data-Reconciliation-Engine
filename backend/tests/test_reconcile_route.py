"""Integration tests for POST /api/reconcile/medication — LLM is mocked."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

MOCK_RECONCILE = {
    "reconciled_medication": "Metformin 500mg twice daily",
    "confidence_score": 0.88,
    "reasoning": "Primary care record is most recent. Dose reduction appropriate given eGFR 45.",
    "recommended_actions": ["Update Hospital EHR", "Verify with pharmacist"],
    "clinical_safety_check": "PASSED",
}


def test_reconcile_medication_success(client: TestClient, auth_headers: dict) -> None:
    with patch("app.main.reconcile_medication", new=AsyncMock(return_value=MOCK_RECONCILE)):
        payload = {
            "patient_context": {
                "age": 67,
                "conditions": ["Type 2 Diabetes", "Hypertension"],
                "recent_labs": {"eGFR": 45},
            },
            "sources": [
                {"system": "Hospital EHR", "medication": "Metformin 1000mg twice daily",
                 "last_updated": "2024-10-15", "source_reliability": "high"},
                {"system": "Primary Care", "medication": "Metformin 500mg twice daily",
                 "last_updated": "2025-01-20", "source_reliability": "high"},
            ],
        }
        r = client.post("/api/reconcile/medication", json=payload, headers=auth_headers)

    assert r.status_code == 200
    body = r.json()
    assert body["reconciled_medication"] == "Metformin 500mg twice daily"
    assert body["confidence_score"] == 0.88
    assert body["clinical_safety_check"] == "PASSED"
    assert isinstance(body["recommended_actions"], list)
    assert len(body["recommended_actions"]) == 2


def test_reconcile_requires_auth(client: TestClient) -> None:
    r = client.post("/api/reconcile/medication", json={"sources": []})
    assert r.status_code == 401


def test_reconcile_rejects_missing_sources(client: TestClient, auth_headers: dict) -> None:
    r = client.post("/api/reconcile/medication", json={}, headers=auth_headers)
    assert r.status_code == 422
