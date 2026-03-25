"""Integration tests for POST /api/validate/data-quality — LLM is mocked."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

MOCK_DQ = {
    "overall_score": 62,
    "breakdown": {
        "completeness": 60,
        "accuracy": 50,
        "timeliness": 70,
        "clinical_plausibility": 40,
    },
    "issues_detected": [
        {"field": "allergies", "issue": "No allergies documented", "severity": "medium"},
        {"field": "vital_signs.blood_pressure", "issue": "Blood pressure 340/180 is implausible", "severity": "high"},
    ],
}


def test_data_quality_success(client: TestClient, auth_headers: dict) -> None:
    with patch("app.main.validate_data_quality", new=AsyncMock(return_value=MOCK_DQ)):
        payload = {
            "demographics": {"name": "John Doe", "dob": "1955-03-15", "gender": "M"},
            "medications": ["Metformin 500mg", "Lisinopril 10mg"],
            "allergies": [],
            "conditions": ["Type 2 Diabetes"],
            "vital_signs": {"blood_pressure": "340/180", "heart_rate": 72},
            "last_updated": "2024-06-15",
        }
        r = client.post("/api/validate/data-quality", json=payload, headers=auth_headers)

    assert r.status_code == 200
    body = r.json()
    assert body["overall_score"] == 62
    assert body["breakdown"]["clinical_plausibility"] == 40
    assert any(i["severity"] == "high" for i in body["issues_detected"])


def test_data_quality_requires_auth(client: TestClient) -> None:
    r = client.post("/api/validate/data-quality", json={})
    assert r.status_code == 401


def test_data_quality_accepts_empty_record(client: TestClient, auth_headers: dict) -> None:
    empty_mock = {
        "overall_score": 0,
        "breakdown": {"completeness": 0, "accuracy": 0, "timeliness": 0, "clinical_plausibility": 0},
        "issues_detected": [],
    }
    with patch("app.main.validate_data_quality", new=AsyncMock(return_value=empty_mock)):
        r = client.post("/api/validate/data-quality", json={}, headers=auth_headers)
    assert r.status_code == 200
