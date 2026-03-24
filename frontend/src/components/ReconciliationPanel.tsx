import { useState } from "react";
import { postJson } from "../api/client";
import type { MedicationSource, ReconcileRequest, ReconcileResponse, Reliability } from "../types";

// ── Helpers ──────────────────────────────────────────────────────────────

function parseLabs(text: string): Record<string, string | number> {
  const result: Record<string, string | number> = {};
  text.split("\n").forEach((line) => {
    const idx = line.indexOf(":");
    if (idx === -1) return;
    const key = line.slice(0, idx).trim();
    const raw = line.slice(idx + 1).trim();
    if (!key || !raw) return;
    const num = parseFloat(raw);
    result[key] = isNaN(num) ? raw : num;
  });
  return result;
}

function confidenceColor(score: number) {
  if (score >= 0.75) return "bg-green-500";
  if (score >= 0.5) return "bg-yellow-400";
  return "bg-red-500";
}

function safetyBadge(check: string) {
  if (check === "PASSED") return "bg-green-100 text-green-800";
  if (check === "FAILED") return "bg-red-100 text-red-800";
  return "bg-yellow-100 text-yellow-800";
}

const BLANK_SOURCE: MedicationSource = {
  system: "",
  medication: "",
  last_updated: "",
  source_reliability: "high",
};

// ── Component ────────────────────────────────────────────────────────────

export function ReconciliationPanel() {
  const [age, setAge] = useState("");
  const [conditions, setConditions] = useState("");
  const [labs, setLabs] = useState("");
  const [sources, setSources] = useState<MedicationSource[]>([{ ...BLANK_SOURCE }]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReconcileResponse | null>(null);
  const [decision, setDecision] = useState<"approved" | "rejected" | null>(null);

  function updateSource(i: number, field: keyof MedicationSource, value: string) {
    setSources((prev) => prev.map((s, idx) => (idx === i ? { ...s, [field]: value } : s)));
  }

  function addSource() {
    setSources((prev) => [...prev, { ...BLANK_SOURCE }]);
  }

  function removeSource(i: number) {
    setSources((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setDecision(null);

    try {
      const body: ReconcileRequest = {
        patient_context: {
          age: age ? parseInt(age) : undefined,
          conditions: conditions.split(",").map((s) => s.trim()).filter(Boolean),
          recent_labs: parseLabs(labs),
        },
        sources: sources.filter((s) => s.system && s.medication),
      };
      const res = await postJson<ReconcileResponse>("/api/reconcile/medication", body);
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
        {/* Patient context */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <h3 className="font-semibold text-gray-700">Patient context</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">Age</label>
              <input
                type="number"
                min={0}
                max={150}
                value={age}
                onChange={(e) => setAge(e.target.value)}
                placeholder="e.g. 67"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">
                Conditions <span className="text-gray-400">(comma-separated)</span>
              </label>
              <input
                type="text"
                value={conditions}
                onChange={(e) => setConditions(e.target.value)}
                placeholder="Type 2 Diabetes, Hypertension"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              Recent labs <span className="text-gray-400">(one per line: key: value)</span>
            </label>
            <textarea
              rows={3}
              value={labs}
              onChange={(e) => setLabs(e.target.value)}
              placeholder={"eGFR: 45\nHbA1c: 7.2"}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
        </div>

        {/* Sources */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-gray-700">Medication sources</h3>
            <button
              type="button"
              onClick={addSource}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              + Add source
            </button>
          </div>

          {sources.map((src, i) => (
            <div key={i} className="grid grid-cols-1 sm:grid-cols-4 gap-3 p-4 rounded-lg bg-gray-50 border border-gray-100">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">System</label>
                <input
                  type="text"
                  value={src.system}
                  onChange={(e) => updateSource(i, "system", e.target.value)}
                  placeholder="Hospital EHR"
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Medication</label>
                <input
                  type="text"
                  value={src.medication}
                  onChange={(e) => updateSource(i, "medication", e.target.value)}
                  placeholder="Metformin 500mg"
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Last updated</label>
                <input
                  type="date"
                  value={src.last_updated}
                  onChange={(e) => updateSource(i, "last_updated", e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-500 mb-1">Reliability</label>
                  <select
                    value={src.source_reliability}
                    onChange={(e) => updateSource(i, "source_reliability", e.target.value as Reliability)}
                    className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                  >
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                {sources.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeSource(i)}
                    className="mb-0.5 text-red-400 hover:text-red-600 text-lg leading-none"
                    title="Remove source"
                  >
                    ×
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || sources.filter((s) => s.system && s.medication).length === 0}
          className="w-full rounded-lg bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Reconciling…" : "Reconcile medication"}
        </button>
      </form>

      {/* ── Result ── */}
      {result && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-5">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Reconciled medication</p>
              <p className="text-2xl font-bold text-gray-900">{result.reconciled_medication}</p>
            </div>
            <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${safetyBadge(result.clinical_safety_check)}`}>
              {result.clinical_safety_check === "PASSED" ? "✓ " : "✕ "}{result.clinical_safety_check}
            </span>
          </div>

          {/* Confidence score */}
          <div>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="font-medium text-gray-600">Confidence score</span>
              <span className="font-bold text-gray-800">{Math.round(result.confidence_score * 100)}%</span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-gray-100 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${confidenceColor(result.confidence_score)}`}
                style={{ width: `${result.confidence_score * 100}%` }}
              />
            </div>
          </div>

          {/* Reasoning */}
          <div>
            <p className="text-sm font-medium text-gray-600 mb-1">Clinical reasoning</p>
            <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-4 border border-gray-100">
              {result.reasoning}
            </p>
          </div>

          {/* Recommended actions */}
          {result.recommended_actions.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-600 mb-2">Recommended actions</p>
              <ul className="space-y-1.5">
                {result.recommended_actions.map((action, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="mt-0.5 text-blue-500 shrink-0">→</span>
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Approve / Reject */}
          {decision === null ? (
            <div className="flex gap-3 pt-2 border-t border-gray-100">
              <button
                onClick={() => setDecision("approved")}
                className="flex-1 rounded-lg bg-green-600 px-4 py-2.5 text-white text-sm font-medium hover:bg-green-700 transition-colors"
              >
                ✓ Approve suggestion
              </button>
              <button
                onClick={() => setDecision("rejected")}
                className="flex-1 rounded-lg border border-red-300 text-red-600 px-4 py-2.5 text-sm font-medium hover:bg-red-50 transition-colors"
              >
                ✕ Reject suggestion
              </button>
            </div>
          ) : (
            <div className={`rounded-lg px-4 py-3 text-sm font-medium flex items-center justify-between ${decision === "approved" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
              <span>{decision === "approved" ? "✓ Suggestion approved" : "✕ Suggestion rejected"}</span>
              <button onClick={() => setDecision(null)} className="text-xs underline opacity-60 hover:opacity-100">
                Undo
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
