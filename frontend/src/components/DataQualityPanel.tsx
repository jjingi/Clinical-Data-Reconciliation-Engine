import { useState } from "react";
import { postJson } from "../api/client";
import type { DataQualityResponse, Severity } from "../types";

// ── Helpers ──────────────────────────────────────────────────────────────

function scoreColor(score: number) {
  if (score >= 75) return "bg-green-500";
  if (score >= 50) return "bg-yellow-400";
  return "bg-red-500";
}

function scoreText(score: number) {
  if (score >= 75) return "text-green-700";
  if (score >= 50) return "text-yellow-700";
  return "text-red-600";
}

function scoreBg(score: number) {
  if (score >= 75) return "bg-green-50 border-green-200";
  if (score >= 50) return "bg-yellow-50 border-yellow-200";
  return "bg-red-50 border-red-200";
}

function severityBadge(severity: Severity) {
  if (severity === "high") return "bg-red-100 text-red-700";
  if (severity === "medium") return "bg-yellow-100 text-yellow-700";
  return "bg-green-100 text-green-700";
}

const BREAKDOWN_LABELS: Record<string, string> = {
  completeness: "Completeness",
  accuracy: "Accuracy",
  timeliness: "Timeliness",
  clinical_plausibility: "Clinical plausibility",
};

// ── Component ────────────────────────────────────────────────────────────

export function DataQualityPanel() {
  // Demographics
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");

  // Clinical fields (one per line)
  const [medications, setMedications] = useState("");
  const [allergies, setAllergies] = useState("");
  const [conditions, setConditions] = useState("");

  // Vitals
  const [bloodPressure, setBloodPressure] = useState("");
  const [heartRate, setHeartRate] = useState("");

  const [lastUpdated, setLastUpdated] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DataQualityResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const body = {
        demographics: { name, dob, gender },
        medications: medications.split("\n").map((s) => s.trim()).filter(Boolean),
        allergies: allergies.split("\n").map((s) => s.trim()).filter(Boolean),
        conditions: conditions.split("\n").map((s) => s.trim()).filter(Boolean),
        vital_signs: {
          blood_pressure: bloodPressure,
          heart_rate: heartRate ? parseInt(heartRate) : undefined,
        },
        last_updated: lastUpdated || undefined,
      };
      const res = await postJson<DataQualityResponse>("/api/validate/data-quality", body);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Form ── */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Demographics */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <h3 className="font-semibold text-gray-700">Demographics</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Full name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="John Doe"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Date of birth</label>
              <input
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Gender</label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                <option value="">Not specified</option>
                <option value="M">Male</option>
                <option value="F">Female</option>
                <option value="O">Other</option>
              </select>
            </div>
          </div>
        </div>

        {/* Clinical data */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <h3 className="font-semibold text-gray-700">Clinical data</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">
                Medications <span className="text-gray-400">(one per line)</span>
              </label>
              <textarea
                rows={4}
                value={medications}
                onChange={(e) => setMedications(e.target.value)}
                placeholder={"Metformin 500mg\nLisinopril 10mg"}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">
                Allergies <span className="text-gray-400">(one per line)</span>
              </label>
              <textarea
                rows={4}
                value={allergies}
                onChange={(e) => setAllergies(e.target.value)}
                placeholder={"Penicillin\nSulfa drugs"}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">
                Conditions <span className="text-gray-400">(one per line)</span>
              </label>
              <textarea
                rows={4}
                value={conditions}
                onChange={(e) => setConditions(e.target.value)}
                placeholder={"Type 2 Diabetes\nHypertension"}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
          </div>
        </div>

        {/* Vitals + metadata */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <h3 className="font-semibold text-gray-700">Vital signs &amp; record metadata</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Blood pressure</label>
              <input
                type="text"
                value={bloodPressure}
                onChange={(e) => setBloodPressure(e.target.value)}
                placeholder="120/80"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Heart rate (bpm)</label>
              <input
                type="number"
                value={heartRate}
                onChange={(e) => setHeartRate(e.target.value)}
                placeholder="72"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Record last updated</label>
              <input
                type="date"
                value={lastUpdated}
                onChange={(e) => setLastUpdated(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
          </div>
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Validating…" : "Validate data quality"}
        </button>
      </form>

      {/* ── Result ── */}
      {result && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-6">
          {/* Overall score */}
          <div className={`rounded-lg border p-5 flex items-center justify-between ${scoreBg(result.overall_score)}`}>
            <div>
              <p className="text-sm font-medium text-gray-600">Overall data quality score</p>
              <p className={`text-5xl font-bold mt-1 ${scoreText(result.overall_score)}`}>
                {result.overall_score}
                <span className="text-xl font-medium opacity-60">/100</span>
              </p>
            </div>
            <div className={`text-4xl ${scoreText(result.overall_score)}`}>
              {result.overall_score >= 75 ? "✓" : result.overall_score >= 50 ? "⚠" : "✕"}
            </div>
          </div>

          {/* Breakdown */}
          <div>
            <p className="text-sm font-semibold text-gray-600 mb-3">Score breakdown</p>
            <div className="space-y-3">
              {(Object.keys(BREAKDOWN_LABELS) as (keyof typeof result.breakdown)[]).map((key) => {
                const score = result.breakdown[key];
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-600">{BREAKDOWN_LABELS[key]}</span>
                      <span className={`font-semibold ${scoreText(score)}`}>{score}</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${scoreColor(score)}`}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Issues */}
          {result.issues_detected.length > 0 && (
            <div>
              <p className="text-sm font-semibold text-gray-600 mb-3">Issues detected</p>
              <div className="space-y-2">
                {result.issues_detected.map((issue, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50 p-3">
                    <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${severityBadge(issue.severity)}`}>
                      {issue.severity}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-mono text-gray-500">{issue.field}</p>
                      <p className="text-sm text-gray-700 mt-0.5">{issue.issue}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
