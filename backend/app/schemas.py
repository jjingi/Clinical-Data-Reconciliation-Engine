"""Pydantic models — match the assessment API contracts."""

from typing import Any
from pydantic import BaseModel, Field


# ── POST /api/reconcile/medication ──────────────────────────────────────


class PatientContext(BaseModel):
    age: int | None = None
    conditions: list[str] = Field(default_factory=list)
    recent_labs: dict[str, Any] = Field(default_factory=dict)


class MedicationSourceRecord(BaseModel):
    system: str
    medication: str
    last_updated: str | None = None
    last_filled: str | None = None
    source_reliability: str | None = None


class MedicationReconcileRequest(BaseModel):
    patient_context: PatientContext = Field(default_factory=PatientContext)
    sources: list[MedicationSourceRecord]


class MedicationReconcileResponse(BaseModel):
    reconciled_medication: str
    confidence_score: float
    reasoning: str
    recommended_actions: list[str] = Field(default_factory=list)
    clinical_safety_check: str


# ── POST /api/validate/data-quality ─────────────────────────────────────


class DataQualityRequest(BaseModel):
    demographics: dict[str, Any] = Field(default_factory=dict)
    medications: list[str] = Field(default_factory=list)
    allergies: list[Any] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    vital_signs: dict[str, Any] = Field(default_factory=dict)
    last_updated: str | None = None


class QualityBreakdown(BaseModel):
    completeness: int
    accuracy: int
    timeliness: int
    clinical_plausibility: int


class DataQualityIssue(BaseModel):
    field: str
    issue: str
    severity: str


class DataQualityResponse(BaseModel):
    overall_score: int
    breakdown: QualityBreakdown
    issues_detected: list[DataQualityIssue] = Field(default_factory=list)
