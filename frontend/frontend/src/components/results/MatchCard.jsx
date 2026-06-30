import { useState } from "react";
import { ScoreBar } from "./ScoreBar";
import { StatusBadge } from "./StatusBadge";
import { ExplainPanel } from "./ExplainPanel";
import { OverrideModal } from "./OverrideModal";

function DataField({ label, value, highlight }) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className={`text-sm font-medium font-mono truncate
        ${highlight ? "text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded" : "text-gray-800"}`}>
        {value || <span className="text-gray-300 italic">—</span>}
      </p>
    </div>
  );
}

export function MatchCard({ match, onOverride }) {
  const [open, setOpen]         = useState(false);
  const [showExplain, setExplain] = useState(false);
  const [showOverride, setOverride] = useState(false);

  const { invoice, ledger_entry: led, score, status,
          field_breakdown: bd, is_overridden, override_status, override_note } = match;

  const displayStatus = override_status || status;

  return (
    <>
      <div className={`bg-white rounded-2xl border shadow-sm overflow-hidden transition-all
        ${open ? "shadow-md" : "hover:shadow-md"}
        ${displayStatus === "auto_match" ? "border-emerald-200" :
          displayStatus === "review"     ? "border-amber-200"   :
                                           "border-red-200"}`}>

        {/* ── Header row ─────────────────────────────────────────── */}
        <div className="flex items-center gap-4 p-4 cursor-pointer"
          onClick={() => setOpen(!open)}>

          {/* chevron */}
          <span className={`text-gray-400 transition-transform duration-200 ${open ? "rotate-90" : ""}`}>
            ›
          </span>

          {/* invoice ref */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono font-bold text-gray-900 text-sm">
                {invoice.invoice_number || "No number"}
              </span>
              <span className="text-gray-300">↔</span>
              <span className="font-mono font-bold text-gray-900 text-sm">
                {led.reference || "No ref"}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5 truncate">
              {invoice.vendor_name} · {invoice.date}
            </p>
          </div>

          {/* score bar */}
          <div className="w-36 shrink-0">
            <ScoreBar score={score} />
          </div>

          {/* badge */}
          <div className="shrink-0">
            <StatusBadge status={displayStatus} overridden={is_overridden} />
          </div>
        </div>

        {/* ── Expanded body ───────────────────────────────────────── */}
        {open && (
          <div className="border-t border-gray-100 p-4 space-y-4">

            {/* Side-by-side comparison */}
            <div className="grid grid-cols-2 gap-4">
              {/* Invoice side */}
              <div className="bg-blue-50 rounded-xl p-4 space-y-3">
                <p className="text-xs font-bold text-blue-600 uppercase tracking-wide mb-2">
                  📄 Invoice
                </p>
                <DataField label="Invoice Number" value={invoice.invoice_number}
                  highlight={bd.invoice_number.score >= 0.9} />
                <DataField label="Vendor"    value={invoice.vendor_name}
                  highlight={bd.vendor.score >= 0.9} />
                <DataField label="Date"      value={invoice.date}
                  highlight={bd.date.score >= 0.9} />
                <DataField label="Amount"    value={invoice.amount}
                  highlight={bd.amount.score >= 0.9} />
                {invoice.source_file && (
                  <p className="text-xs text-blue-400 truncate">
                    Source: {invoice.source_file}
                  </p>
                )}
              </div>

              {/* Ledger side */}
              <div className="bg-purple-50 rounded-xl p-4 space-y-3">
                <p className="text-xs font-bold text-purple-600 uppercase tracking-wide mb-2">
                  📒 Ledger Entry
                </p>
                <DataField label="Reference"  value={led.reference}
                  highlight={bd.invoice_number.score >= 0.9} />
                <DataField label="Vendor"     value={led.vendor}
                  highlight={bd.vendor.score >= 0.9} />
                <DataField label="Date"       value={led.date}
                  highlight={bd.date.score >= 0.9} />
                <DataField label="Debit"      value={led.debit}
                  highlight={bd.amount.score >= 0.9} />
                {led.credit && <DataField label="Credit" value={led.credit} />}
                {led.source_file && (
                  <p className="text-xs text-purple-400 truncate">
                    Source: {led.source_file}
                  </p>
                )}
              </div>
            </div>

            {/* Override note */}
            {is_overridden && override_note && (
              <div className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-2">
                <p className="text-xs text-gray-500">
                  <span className="font-semibold">Override note:</span> {override_note}
                </p>
              </div>
            )}

            {/* Explainability toggle */}
            <button onClick={() => setExplain(!showExplain)}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium
                flex items-center gap-1 transition">
              {showExplain ? "▲ Hide" : "▼ Show"} score breakdown
            </button>

            {showExplain && (
              <ExplainPanel breakdown={bd} totalScore={score} />
            )}

            {/* Actions */}
            <div className="flex justify-end">
              <button onClick={() => setOverride(true)}
                className="px-4 py-2 text-sm font-medium border border-gray-300
                  rounded-xl hover:bg-gray-50 text-gray-700 transition">
                ✏️ Override decision
              </button>
            </div>
          </div>
        )}
      </div>

      {showOverride && (
        <OverrideModal
          match={match}
          onConfirm={onOverride}
          onClose={() => setOverride(false)}
        />
      )}
    </>
  );
}
