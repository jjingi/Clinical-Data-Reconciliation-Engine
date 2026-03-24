import { useState } from "react";
import { DataQualityPanel } from "./components/DataQualityPanel";
import { ReconciliationPanel } from "./components/ReconciliationPanel";

const TABS = [
  { id: "reconcile", label: "Medication reconciliation" },
  { id: "quality", label: "Data quality" },
] as const;

type Tab = (typeof TABS)[number]["id"];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("reconcile");

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white shadow-sm">
        <div className="mx-auto max-w-4xl px-6 py-5">
          <h1 className="text-xl font-bold text-gray-800">Clinical data reconciliation</h1>
          <p className="text-sm text-gray-500 mt-0.5">AI-assisted EHR reconciliation engine</p>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-1 rounded-lg bg-gray-200 p-1 mb-8">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-800"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === "reconcile" && <ReconciliationPanel />}
        {activeTab === "quality" && <DataQualityPanel />}
      </div>
    </div>
  );
}
