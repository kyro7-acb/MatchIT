import { api } from "../../utils/api";

function Stat({ label, value, color }) {
  return (
    <div className="flex flex-col items-center">
      <span className={`text-3xl font-bold ${color}`}>{value}</span>
      <span className="text-xs text-gray-500 mt-1">{label}</span>
    </div>
  );
}

export function SummaryBar({ summary, sessionId }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex gap-8">
          <Stat label="Auto Match"  value={summary.auto_match_count} color="text-emerald-600" />
          <Stat label="Review"      value={summary.review_count}     color="text-amber-500"   />
          <Stat label="Unmatched"   value={summary.unmatched_count}  color="text-red-500"     />
          <Stat label="Skipped"     value={summary.skipped_count}    color="text-gray-400"    />
        </div>

        <div className="flex gap-2">
          <a
            href={api.exportUrl(sessionId, "csv")}
            target="_blank" rel="noreferrer"
            className="px-4 py-2 text-sm font-medium border border-gray-300
              rounded-xl hover:bg-gray-50 text-gray-700 transition">
            ⬇ Export CSV
          </a>
          <a
            href={api.exportUrl(sessionId, "json")}
            target="_blank" rel="noreferrer"
            className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700
              text-white rounded-xl transition">
            ⬇ Export JSON
          </a>
        </div>
      </div>

      {/* Progress bar breakdown */}
      {summary.total_invoices > 0 && (
        <div className="mt-5">
          <div className="flex rounded-full overflow-hidden h-2.5 bg-gray-100">
            <div className="bg-emerald-500 transition-all"
              style={{ width: `${(summary.auto_match_count / summary.total_invoices) * 100}%` }} />
            <div className="bg-amber-400 transition-all"
              style={{ width: `${(summary.review_count / summary.total_invoices) * 100}%` }} />
            <div className="bg-red-400 transition-all"
              style={{ width: `${(summary.unmatched_count / summary.total_invoices) * 100}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-1.5 text-right">
            {summary.total_invoices} invoices · {summary.total_ledger} ledger entries
          </p>
        </div>
      )}
    </div>
  );
}
