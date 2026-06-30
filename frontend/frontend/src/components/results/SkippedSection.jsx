import { useState } from "react";

export function SkippedSection({ items }) {
  const [open, setOpen] = useState(false);
  if (!items?.length) return null;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-100 transition">
        <div className="flex items-center gap-3">
          <span className="text-lg">⚠️</span>
          <div>
            <p className="font-semibold text-gray-800">
              {items.length} Skipped / Low-confidence Item{items.length > 1 ? "s" : ""}
            </p>
            <p className="text-xs text-gray-500">
              Filtered out before matching — click to see reasons
            </p>
          </div>
        </div>
        <span className={`text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
      </button>

      {open && (
        <div className="border-t border-gray-200 divide-y divide-gray-100">
          {items.map((item, i) => (
            <div key={i} className="px-5 py-3 flex items-start gap-4">
              <span className={`mt-0.5 text-xs font-bold px-2 py-0.5 rounded-full shrink-0
                ${item.item_type === "invoice"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-purple-100 text-purple-700"}`}>
                {item.item_type === "invoice" ? "INV" : "LED"}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-800 font-mono">
                  {item.item_ref || "—"}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">{item.reason}</p>
                {item.detail && (
                  <p className="text-xs text-gray-400 mt-0.5 font-mono">
                    {JSON.stringify(item.detail)}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
