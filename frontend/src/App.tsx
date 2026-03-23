import { DataQualityPanel } from "./components/DataQualityPanel";
import { ReconciliationPanel } from "./components/ReconciliationPanel";

export default function App() {
  return (
    <main className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <h1 className="text-3xl font-bold mb-8">Clinical data reconciliation</h1>
        <div className="space-y-8">
          <ReconciliationPanel />
          <DataQualityPanel />
        </div>
      </div>
    </main>
  );
}
