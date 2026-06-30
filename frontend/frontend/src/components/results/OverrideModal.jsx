import { useState } from "react";

const OPTIONS = [
  { value: "confirmed", label: "Confirm Match",  color: "bg-blue-600 hover:bg-blue-700"    },
  { value: "rejected",  label: "Reject Match",   color: "bg-red-600 hover:bg-red-700"      },
  { value: "review",    label: "Flag for Review", color: "bg-amber-500 hover:bg-amber-600" },
];

export function OverrideModal({ match, onConfirm, onClose }) {
  const [status, setStatus] = useState("confirmed");
  const [note, setNote]     = useState("");
  const [busy, setBusy]     = useState(false);

  const submit = async () => {
    setBusy(true);
    await onConfirm(match.match_id, status, note);
    setBusy(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-1">Override Match Decision</h3>
        <p className="text-sm text-gray-500 mb-5">
          Invoice <span className="font-mono font-semibold">{match.invoice.invoice_number}</span>
          {" "}↔{" "}
          Ledger <span className="font-mono font-semibold">{match.ledger_entry.reference}</span>
        </p>

        <div className="space-y-2 mb-4">
          {OPTIONS.map((o) => (
            <label key={o.value}
              className={`flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition
                ${status === o.value ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"}`}>
              <input type="radio" name="status" value={o.value}
                checked={status === o.value}
                onChange={() => setStatus(o.value)}
                className="accent-blue-600" />
              <span className="font-medium text-sm text-gray-800">{o.label}</span>
            </label>
          ))}
        </div>

        <textarea
          className="w-full border border-gray-300 rounded-xl p-3 text-sm resize-none
            focus:outline-none focus:ring-2 focus:ring-blue-500 mb-5"
          rows={2}
          placeholder="Optional note (reason for override)…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />

        <div className="flex gap-3">
          <button onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-xl text-sm font-medium
              text-gray-700 hover:bg-gray-50 transition">
            Cancel
          </button>
          <button onClick={submit} disabled={busy}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl
              text-sm font-medium transition disabled:opacity-50">
            {busy ? "Saving…" : "Save Override"}
          </button>
        </div>
      </div>
    </div>
  );
}
