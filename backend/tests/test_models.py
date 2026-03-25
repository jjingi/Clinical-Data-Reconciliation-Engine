from app.schemas import MedicationReconcileRequest, MedicationSourceRecord


def test_medication_request_parses_assessment_example() -> None:
    data = {
        "patient_context": {"age": 67, "conditions": ["Type 2 Diabetes"], "recent_labs": {"eGFR": 45}},
        "sources": [
            {
                "system": "Hospital EHR",
                "medication": "Metformin 1000mg twice daily",
                "last_updated": "2024-10-15",
                "source_reliability": "high",
            }
        ],
    }
    req = MedicationReconcileRequest.model_validate(data)
    assert req.patient_context.age == 67
    assert len(req.sources) == 1
    assert isinstance(req.sources[0], MedicationSourceRecord)
