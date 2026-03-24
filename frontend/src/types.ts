export type Reliability = "high" | "medium" | "low";
export type Severity = "high" | "medium" | "low";

// ── Reconciliation ───────────────────────────────────────────────────────

export interface MedicationSource {
  system: string;
  medication: string;
  last_updated: string;
  source_reliability: Reliability;
}

export interface ReconcileRequest {
  patient_context: {
    age: number | undefined;
    conditions: string[];
    recent_labs: Record<string, string | number>;
  };
  sources: MedicationSource[];
}

export interface ReconcileResponse {
  reconciled_medication: string;
  confidence_score: number;
  reasoning: string;
  recommended_actions: string[];
  clinical_safety_check: string;
}

// ── Data quality ─────────────────────────────────────────────────────────

export interface DataQualityResponse {
  overall_score: number;
  breakdown: {
    completeness: number;
    accuracy: number;
    timeliness: number;
    clinical_plausibility: number;
  };
  issues_detected: Array<{
    field: string;
    issue: string;
    severity: Severity;
  }>;
}
