"""
Real end-to-end integration tests using PyHealth MIMIC-III synthetic data.

- Loads real patient data from Synthetic MIMIC-III (public, no credentials needed)
- Sends it to the live FastAPI endpoints
- The endpoints call the real OpenAI API (gpt-5.4-mini) — no mocking

Requires OPENAI_API_KEY and API_KEY to be set in backend/.env
"""

import pytest
from pyhealth.data import Patient
from pyhealth.datasets import MIMIC3Dataset
from fastapi.testclient import TestClient

from app.main import app, settings

SYNTHETIC_MIMIC_ROOT = "https://storage.googleapis.com/pyhealth/Synthetic_MIMIC-III/"


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mimic() -> MIMIC3Dataset:
    """Load Synthetic MIMIC-III (downloads ~5 MB on first run, cached after)."""
    return MIMIC3Dataset(
        root=SYNTHETIC_MIMIC_ROOT,
        tables=["prescriptions", "diagnoses_icd"],
    )


@pytest.fixture(scope="module")
def patient(mimic: MIMIC3Dataset) -> Patient:
    return mimic.get_patient("1")


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def auth() -> dict:
    return {"X-API-Key": settings.api_key}


# ── Helpers ───────────────────────────────────────────────────────────────


def format_drug(event) -> str:
    drug = event.attr_dict.get("drug", "")
    strength = event.attr_dict.get("prod_strength", "")
    route = event.attr_dict.get("route", "")
    return f"{drug} {strength} {route}".strip()


def build_reconcile_payload(patient: Patient, drug_fragment: str, age: int = None, conditions: list = None) -> dict:
    """
    Find prescriptions matching drug_fragment in the MIMIC patient,
    map each to a different EHR source system, and return the API payload.
    """
    SYSTEMS = [
        ("Hospital EHR", "high"),
        ("Primary Care", "high"),
        ("Pharmacy", "medium"),
    ]
    events = patient.get_events("prescriptions")
    matching = [e for e in events if drug_fragment.lower() in e.attr_dict.get("drug", "").lower()]

    sources = []
    for i, event in enumerate(matching[:3]):
        system, reliability = SYSTEMS[i % len(SYSTEMS)]
        source = {
            "system": system,
            "medication": format_drug(event),
            "source_reliability": reliability,
        }
        if event.timestamp:
            source["last_updated"] = event.timestamp.date().isoformat()
        sources.append(source)

    # Ensure at least 2 sources to make it a genuine reconciliation scenario
    if len(sources) == 1:
        sources.append({
            "system": "Primary Care",
            "medication": sources[0]["medication"],
            "source_reliability": "high",
            "last_updated": sources[0].get("last_updated", "2025-01-01"),
        })

    return {
        "patient_context": {
            "age": age,
            "conditions": conditions or [],
            "recent_labs": {},
        },
        "sources": sources,
    }


def build_quality_payload(patient: Patient) -> dict:
    """Build a data-quality payload from all of a MIMIC patient's available events."""
    prescriptions = patient.get_events("prescriptions")
    diagnoses = patient.get_events("diagnoses_icd")

    medications = list({format_drug(e) for e in prescriptions if e.attr_dict.get("drug")})
    conditions = list({e.attr_dict.get("icd9_code", "") for e in diagnoses if e.attr_dict.get("icd9_code")})

    timestamps = [e.timestamp for e in prescriptions + diagnoses if e.timestamp]
    last_updated = max(timestamps).date().isoformat() if timestamps else None

    return {
        "demographics": {"name": "MIMIC Synthetic Patient 1", "source": "Synthetic MIMIC-III"},
        "medications": medications,
        "allergies": [],
        "conditions": conditions,
        "vital_signs": {},
        "last_updated": last_updated,
    }


# ── MIMIC data model tests (no network/API calls) ─────────────────────────


def test_mimic_patient_has_prescriptions(patient: Patient) -> None:
    events = patient.get_events("prescriptions")
    assert len(events) > 0
    assert events[0].event_type == "prescriptions"
    assert "drug" in events[0].attr_dict


def test_mimic_patient_has_diagnoses(patient: Patient) -> None:
    events = patient.get_events("diagnoses_icd")
    assert len(events) > 0
    assert "icd9_code" in events[0].attr_dict


def test_mimic_prescriptions_have_drug_and_strength(patient: Patient) -> None:
    for event in patient.get_events("prescriptions")[:5]:
        assert event.attr_dict.get("drug"), f"Missing drug field in: {event}"
        assert event.attr_dict.get("prod_strength"), f"Missing prod_strength in: {event}"


def test_reconcile_payload_has_multiple_sources(patient: Patient) -> None:
    payload = build_reconcile_payload(patient, "Lisinopril")
    assert len(payload["sources"]) >= 2
    for s in payload["sources"]:
        assert s["medication"] != ""
        assert s["system"] in ("Hospital EHR", "Primary Care", "Pharmacy")


def test_quality_payload_has_medications_and_conditions(patient: Patient) -> None:
    payload = build_quality_payload(patient)
    assert len(payload["medications"]) > 0
    assert len(payload["conditions"]) > 0


# ── Real API tests (calls live OpenAI) ───────────────────────────────────


def test_reconcile_lisinopril_from_mimic(client: TestClient, patient: Patient, auth: dict) -> None:
    """
    Take real Lisinopril prescriptions from MIMIC patient 1,
    map to multiple EHR sources, and reconcile with GPT.
    """
    payload = build_reconcile_payload(
        patient,
        drug_fragment="Lisinopril",
        age=60,
        conditions=["Hypertension", "Type 2 Diabetes"],
    )
    r = client.post("/api/reconcile/medication", json=payload, headers=auth)

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()

    print("\n── Lisinopril reconciliation ──────────────────────────")
    print(f"  Reconciled medication : {body['reconciled_medication']}")
    print(f"  Confidence score      : {body['confidence_score']}")
    print(f"  Clinical safety check : {body['clinical_safety_check']}")
    print(f"  Reasoning             : {body['reasoning']}")
    print(f"  Recommended actions   : {body['recommended_actions']}")

    assert isinstance(body["reconciled_medication"], str) and body["reconciled_medication"]
    assert 0.0 <= body["confidence_score"] <= 1.0
    assert isinstance(body["reasoning"], str) and body["reasoning"]
    assert isinstance(body["recommended_actions"], list)
    assert body["clinical_safety_check"] in ("PASSED", "FAILED")


def test_reconcile_acetaminophen_from_mimic(client: TestClient, patient: Patient, auth: dict) -> None:
    """
    Reconcile Acetaminophen records from the MIMIC patient across sources.
    """
    payload = build_reconcile_payload(patient, drug_fragment="Acetaminophen")
    r = client.post("/api/reconcile/medication", json=payload, headers=auth)

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()

    print("\n── Acetaminophen reconciliation ───────────────────────")
    print(f"  Reconciled medication : {body['reconciled_medication']}")
    print(f"  Confidence score      : {body['confidence_score']}")
    print(f"  Clinical safety check : {body['clinical_safety_check']}")
    print(f"  Reasoning             : {body['reasoning']}")

    assert isinstance(body["reconciled_medication"], str) and body["reconciled_medication"]
    assert 0.0 <= body["confidence_score"] <= 1.0
    assert body["clinical_safety_check"] in ("PASSED", "FAILED")


def test_data_quality_mimic_patient(client: TestClient, patient: Patient, auth: dict) -> None:
    """
    Validate data quality of a real MIMIC patient record with GPT.
    Checks that scores are in range and issues list is present.
    """
    payload = build_quality_payload(patient)
    r = client.post("/api/validate/data-quality", json=payload, headers=auth)

    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()

    print("\n── Data quality assessment ────────────────────────────")
    print(f"  Overall score : {body['overall_score']}")
    print(f"  Breakdown     : {body['breakdown']}")
    print(f"  Issues ({len(body['issues_detected'])}):")
    for issue in body["issues_detected"]:
        print(f"    [{issue['severity'].upper()}] {issue['field']}: {issue['issue']}")

    assert 0 <= body["overall_score"] <= 100
    breakdown = body["breakdown"]
    for dim in ("completeness", "accuracy", "timeliness", "clinical_plausibility"):
        assert 0 <= breakdown[dim] <= 100, f"{dim} score out of range: {breakdown[dim]}"
    assert isinstance(body["issues_detected"], list)
