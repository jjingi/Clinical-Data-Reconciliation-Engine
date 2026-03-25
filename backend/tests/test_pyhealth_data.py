"""
Integration tests using the real pyhealth library (pyhealth.readthedocs.io).

pyhealth.data structures used:
  - Event  : a clinical event — event_type, timestamp, and extra keyword fields
  - Patient : patient record backed by a Polars DataFrame; partitioned by event_type

Patient rows are stored as a polars DataFrame in event_type_partitions[("event_type",)].
We read them back with .to_dicts() to convert to our API request format.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import polars as pl
import pytest
from fastapi.testclient import TestClient
from pyhealth.data import Event, Patient


# ── Helpers: PyHealth → API format ──────────────────────────────────────


def patient_to_reconcile_payload(patient: Patient, age: int, conditions: list[str], labs: dict) -> dict:
    """Read medication events from a PyHealth Patient and build our API request."""
    med_df = patient.event_type_partitions.get(("medication",))
    if med_df is None:
        return {"patient_context": {"age": age, "conditions": conditions, "recent_labs": labs}, "sources": []}

    sources = []
    for row in med_df.to_dicts():
        source: dict = {
            "system": row.get("system", "Unknown"),
            "medication": row.get("drug", ""),
            "source_reliability": row.get("source_reliability", "medium"),
        }
        date_str = row["timestamp"].date().isoformat()
        if row.get("record_type") == "pharmacy_fill":
            source["last_filled"] = date_str
        else:
            source["last_updated"] = date_str
        sources.append(source)

    return {
        "patient_context": {"age": age, "conditions": conditions, "recent_labs": labs},
        "sources": sources,
    }


def patient_to_quality_payload(patient: Patient) -> dict:
    """Read all event types from a PyHealth Patient and build a data-quality API request."""
    def get_rows(event_type: str) -> list[dict]:
        df = patient.event_type_partitions.get((event_type,))
        return df.to_dicts() if df is not None else []

    demo = get_rows("demographics")
    demographics = {k: v for k, v in demo[0].items() if k not in ("event_type", "timestamp")} if demo else {}

    medications = [r["drug"] for r in get_rows("medication") if "drug" in r]
    allergies = [r["substance"] for r in get_rows("allergy") if "substance" in r]
    conditions = [r["condition"] for r in get_rows("condition") if "condition" in r]

    vitals = get_rows("vital_signs")
    vital_signs = {k: v for k, v in vitals[0].items() if k not in ("event_type", "timestamp")} if vitals else {}

    all_rows = [r for rows in [demo, get_rows("medication"), get_rows("condition"), vitals]
                for r in rows]
    last_updated = max((r["timestamp"] for r in all_rows), default=datetime.now()).date().isoformat()

    return {
        "demographics": demographics,
        "medications": medications,
        "allergies": allergies,
        "conditions": conditions,
        "vital_signs": vital_signs,
        "last_updated": last_updated,
    }


# ── Fixtures: PDF examples as PyHealth Patients ──────────────────────────


def make_metformin_patient() -> Patient:
    """Metformin reconciliation example from the PDF, as a pyhealth Patient."""
    df = pl.DataFrame({
        "event_type": ["medication", "medication", "medication"],
        "timestamp": [datetime(2024, 10, 15), datetime(2025, 1, 20), datetime(2025, 1, 25)],
        "drug": [
            "Metformin 1000mg twice daily",
            "Metformin 500mg twice daily",
            "Metformin 1000mg daily",
        ],
        "system": ["Hospital EHR", "Primary Care", "Pharmacy"],
        "source_reliability": ["high", "high", "medium"],
        "record_type": ["ehr", "ehr", "pharmacy_fill"],
    })
    return Patient(patient_id="P001", data_source=df)


def make_quality_patient() -> Patient:
    """Data-quality example from the PDF (implausible BP), as a pyhealth Patient."""
    df = pl.DataFrame({
        "event_type": [
            "demographics", "demographics", "demographics",
            "medication", "medication",
            "condition",
            "vital_signs",
        ],
        "timestamp": [datetime(2024, 6, 15)] * 7,
        "name":       ["John Doe", "John Doe", "John Doe", None, None, None, None],
        "dob":        ["1955-03-15", "1955-03-15", "1955-03-15", None, None, None, None],
        "gender":     ["M", "M", "M", None, None, None, None],
        "drug":       [None, None, None, "Metformin 500mg", "Lisinopril 10mg", None, None],
        "condition":  [None, None, None, None, None, "Type 2 Diabetes", None],
        "blood_pressure": [None, None, None, None, None, None, "340/180"],
        "heart_rate": [None, None, None, None, None, None, 72],
    })
    return Patient(patient_id="P002", data_source=df)


# ── Unit tests: PyHealth data model ──────────────────────────────────────


def test_pyhealth_event_creates_with_kwargs() -> None:
    event = Event(
        event_type="medication",
        timestamp=datetime(2025, 1, 20),
        drug="Aspirin 81mg",
        system="Primary Care",
    )
    assert event.event_type == "medication"
    assert event.timestamp == datetime(2025, 1, 20)
    assert event.attr_dict["drug"] == "Aspirin 81mg"


def test_pyhealth_patient_partitions_by_event_type() -> None:
    patient = make_metformin_patient()
    assert ("medication",) in patient.event_type_partitions
    med_df = patient.event_type_partitions[("medication",)]
    assert len(med_df) == 3


def test_pyhealth_patient_get_events_returns_events() -> None:
    patient = make_metformin_patient()
    events = patient.get_events("medication")
    assert len(events) == 3
    assert all(isinstance(e, Event) for e in events)


def test_patient_to_reconcile_payload_maps_all_sources() -> None:
    patient = make_metformin_patient()
    payload = patient_to_reconcile_payload(
        patient, age=67, conditions=["Type 2 Diabetes", "Hypertension"], labs={"eGFR": 45}
    )
    assert payload["patient_context"]["age"] == 67
    assert len(payload["sources"]) == 3
    systems = [s["system"] for s in payload["sources"]]
    assert "Hospital EHR" in systems and "Primary Care" in systems and "Pharmacy" in systems
    pharmacy = next(s for s in payload["sources"] if s["system"] == "Pharmacy")
    assert "last_filled" in pharmacy


def test_patient_to_quality_payload_maps_fields() -> None:
    patient = make_quality_patient()
    payload = patient_to_quality_payload(patient)
    assert "Metformin 500mg" in payload["medications"]
    assert payload["vital_signs"]["blood_pressure"] == "340/180"
    assert "Type 2 Diabetes" in payload["conditions"]


# ── Integration tests: PyHealth Patient → API ────────────────────────────

MOCK_RECONCILE = {
    "reconciled_medication": "Metformin 500mg twice daily",
    "confidence_score": 0.88,
    "reasoning": "Primary care record is most recent. Dose reduction appropriate given eGFR 45.",
    "recommended_actions": ["Update Hospital EHR", "Verify with pharmacist"],
    "clinical_safety_check": "PASSED",
}

MOCK_DQ = {
    "overall_score": 62,
    "breakdown": {"completeness": 60, "accuracy": 50, "timeliness": 70, "clinical_plausibility": 40},
    "issues_detected": [
        {"field": "vital_signs.blood_pressure", "issue": "340/180 is implausible", "severity": "high"},
        {"field": "allergies", "issue": "No allergies documented", "severity": "medium"},
    ],
}


def test_reconcile_endpoint_with_pyhealth_patient(client: TestClient, auth_headers: dict) -> None:
    patient = make_metformin_patient()
    payload = patient_to_reconcile_payload(
        patient, age=67, conditions=["Type 2 Diabetes", "Hypertension"], labs={"eGFR": 45}
    )
    with patch("app.main.reconcile_medication", new=AsyncMock(return_value=MOCK_RECONCILE)):
        r = client.post("/api/reconcile/medication", json=payload, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["reconciled_medication"] == "Metformin 500mg twice daily"
    assert body["confidence_score"] == 0.88
    assert body["clinical_safety_check"] == "PASSED"


def test_data_quality_endpoint_with_pyhealth_patient(client: TestClient, auth_headers: dict) -> None:
    patient = make_quality_patient()
    payload = patient_to_quality_payload(patient)
    with patch("app.main.validate_data_quality", new=AsyncMock(return_value=MOCK_DQ)):
        r = client.post("/api/validate/data-quality", json=payload, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["overall_score"] == 62
    assert any(i["severity"] == "high" for i in body["issues_detected"])
