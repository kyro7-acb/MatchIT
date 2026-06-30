import { ScoreBar } from "./ScoreBar";

const FIELD_META = {
  invoice_number: { label: "Invoice Number", icon: "🔢", weight: "40%" },
  vendor:         { label: "Vendor Name",     icon: "🏢", weight: "25%" },
  date:           { label: "Date",            icon: "📅", weight: "20%" },
  amount:         { label: "Amount",          icon: "💰", weight: "15%" },
};

function FieldRow({ field, data }) {
  const meta = FIELD_META[field];
  const match = data.score >= 0.9;
  const partial = data.score >= 0.6 && data.score < 0.9;

  return (
    <div className="grid grid-cols-[28px_1fr_1fr_120px] gap-3 items-center py-2.5
      border-b border-gray-100 last:border-0">
      {/* icon */}
      <span className="text-lg">{meta.icon}</span>

      {/* field values */}
      <div className="min-w-0">
        <p className="text-xs text-gray-400 mb-0.5">{meta.label} · weight {meta.weight}</p>
        <div className="flex flex-col gap-0.5">
          <span className={`text-xs px-1.5 py-0.5 rounded font-mono truncate
            ${match ? "bg-emerald-50 text-emerald-700" :
              partial ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-600"}`}>
            INV: {data.invoice_value || "—"}
          </span>
          <span className={`text-xs px-1.5 py-0.5 rounded font-mono truncate
            ${match ? "bg-emerald-50 text-emerald-700" :
              partial ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-600"}`}>
            LED: {data.ledger_value || "—"}
          </span>
        </div>
      </div>

      {/* score bar */}
      <div className="min-w-0">
        <ScoreBar score={data.score} size="sm" />
      </div>

      {/* contribution */}
      <div className="text-right">
        <p className="text-xs text-gray-400">Contribution</p>
        <p className="font-mono font-bold text-sm text-gray-700">
          +{data.contribution.toFixed(3)}
        </p>
      </div>
    </div>
  );
}

export function ExplainPanel({ breakdown, totalScore }) {
  return (
    <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Score Breakdown
        </p>
        <span className="text-sm font-mono font-bold text-gray-800">
          Total: {totalScore.toFixed(4)}
        </span>
      </div>

      <div>
        {Object.entries(breakdown).map(([field, data]) => (
          <FieldRow key={field} field={field} data={data} />
        ))}
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200 flex gap-4 text-xs text-gray-500">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500" /> ≥ 0.90 strong match
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-400" /> 0.60–0.89 partial
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-400" /> &lt; 0.60 weak
        </span>
      </div>
    </div>
  );
}
