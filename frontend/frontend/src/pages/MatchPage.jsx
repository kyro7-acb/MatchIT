import { useState } from "react";
import { useMatching } from "../hooks/useMatching";
import { DropZone } from "../components/upload/DropZone";
import { SummaryBar } from "../components/results/SummaryBar";
import { MatchCard } from "../components/results/MatchCard";
import { SkippedSection } from "../components/results/SkippedSection";

const STEP_ORDER = ["idle", "ledger_pending", "ready", "matching", "done"];

function StepIndicator({ step }) {
  const steps = [
    { key: "idle",           label: "Upload Invoices" },
    { key: "ledger_pending", label: "Upload Ledger"   },
    { key: "ready",          label: "Run Matching"    },
    { key: "done",           label: "Results"         },
  ];
  const currentIdx = STEP_ORDER.indexOf(step);

  return (
    <div className="flex items-center gap-0 mb-10">
      {steps.map((s, i) => {
        const done    = STEP_ORDER.indexOf(s.key) < currentIdx;
        const active  = s.key === step || (step === "matching" && s.key === "ready");
        return (
          <div key={s.key} className="flex items-center flex-1">
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                transition-all duration-300
                ${done   ? "bg-emerald-500 text-white" :
                  active ? "bg-blue-600 text-white ring-4 ring-blue-100" :
                           "bg-gray-100 text-gray-400"}`}>
                {done ? "✓" : i + 1}
              </div>
              <span className={`text-xs mt-1.5 font-medium whitespace-nowrap
                ${active ? "text-blue-600" : done ? "text-emerald-600" : "text-gray-400"}`}>
                {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className={`h-0.5 flex-1 mx-2 mt-[-14px] transition-all
                ${done ? "bg-emerald-400" : "bg-gray-200"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ErrorBanner({ message, onDismiss }) {
  return (
    <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-6">
      <span className="text-red-500 text-lg shrink-0">⚠</span>
      <p className="text-sm text-red-700 flex-1">{message}</p>
      <button onClick={onDismiss} className="text-red-400 hover:text-red-600 shrink-0">✕</button>
    </div>
  );
}

function ProgressBanner({ message }) {
  return (
    <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-6">
      <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0" />
      <p className="text-sm text-blue-700">{message}</p>
    </div>
  );
}

export function MatchPage() {
  const {
    step, sessionId, result, error, progress,
    uploadInvoices, uploadLedger, runMatch, overrideMatch, reset,
  } = useMatching();

  const [invoiceFiles, setInvoiceFiles] = useState([]);
  const [ledgerFiles,  setLedgerFiles]  = useState([]);
  const [filter, setFilter]             = useState("all");

  // ── filtered matches ──────────────────────────────────────────────────
  const matches = result?.matches ?? [];
  const filtered = filter === "all" ? matches
    : matches.filter((m) => (m.override_status || m.status) === filter);

  const busy = step === "uploading" || step === "matching";

  // ── handlers ─────────────────────────────────────────────────────────
  const handleInvoiceUpload = async () => {
    if (!invoiceFiles.length) return;
    await uploadInvoices(invoiceFiles);
  };

  const handleLedgerUpload = async () => {
    if (!ledgerFiles.length || !sessionId) return;
    await uploadLedger(sessionId, ledgerFiles);
  };

  const handleMatch = async () => {
    if (!sessionId) return;
    await runMatch(sessionId);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      {/* ── Top nav ───────────────────────────────────────────────── */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🔗</span>
            <span className="font-bold text-gray-900">matchIT</span>
            <span className="text-xs text-gray-400 ml-1">Invoice-to-Ledger Engine</span>
          </div>
          {step !== "idle" && (
            <button onClick={reset}
              className="text-sm text-gray-500 hover:text-gray-800 transition">
              ← New session
            </button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-10">
        {/* Step indicator */}
        <StepIndicator step={step} />

        {/* Error / progress banners */}
        {error    && <ErrorBanner    message={error}    onDismiss={reset} />}
        {progress && !error && <ProgressBanner message={progress} />}

        {/* ── UPLOAD ZONE (idle + ledger_pending + ready) ─────────── */}
        {step !== "done" && step !== "matching" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Invoice drop zone */}
              <div className="space-y-3">
                <DropZone
                  label="Drop Invoice Files Here"
                  icon="📄"
                  files={invoiceFiles}
                  onFiles={setInvoiceFiles}
                  disabled={busy || step === "ledger_pending" || step === "ready"}
                />
                {step === "idle" && (
                  <button
                    onClick={handleInvoiceUpload}
                    disabled={!invoiceFiles.length || busy}
                    className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-40
                      text-white font-semibold rounded-xl transition text-sm">
                    Upload Invoices →
                  </button>
                )}
                {(step === "ledger_pending" || step === "ready") && (
                  <div className="flex items-center gap-2 text-sm text-emerald-600 font-medium px-2">
                    <span>✓</span> Invoices uploaded
                  </div>
                )}
              </div>

              {/* Ledger drop zone */}
              <div className="space-y-3">
                <DropZone
                  label="Drop Ledger Files Here"
                  icon="📒"
                  files={ledgerFiles}
                  onFiles={setLedgerFiles}
                  disabled={busy || step === "idle" || step === "ready"}
                />
                {step === "ledger_pending" && (
                  <button
                    onClick={handleLedgerUpload}
                    disabled={!ledgerFiles.length || busy}
                    className="w-full py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-40
                      text-white font-semibold rounded-xl transition text-sm">
                    Upload Ledger →
                  </button>
                )}
                {step === "ready" && (
                  <div className="flex items-center gap-2 text-sm text-emerald-600 font-medium px-2">
                    <span>✓</span> Ledger uploaded
                  </div>
                )}
              </div>
            </div>

            {/* Run match button */}
            {step === "ready" && (
              <button
                onClick={handleMatch}
                disabled={busy}
                className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600
                  hover:from-blue-700 hover:to-purple-700 text-white font-bold text-lg
                  rounded-2xl shadow-lg hover:shadow-xl transition-all duration-200
                  disabled:opacity-50">
                🚀 Run Matching Pipeline
              </button>
            )}
          </div>
        )}

        {/* ── MATCHING IN PROGRESS ─────────────────────────────────── */}
        {step === "matching" && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent
              rounded-full animate-spin" />
            <p className="text-lg font-semibold text-gray-700">Running matching pipeline…</p>
            <p className="text-sm text-gray-400">
              Extracting → Normalising → Scoring → Optimising → Classifying
            </p>
          </div>
        )}

        {/* ── RESULTS ─────────────────────────────────────────────── */}
        {step === "done" && result && (
          <div className="space-y-6">
            {/* Summary bar */}
            <SummaryBar summary={result.summary} sessionId={sessionId} />

            {/* Filter tabs */}
            <div className="flex gap-2 flex-wrap">
              {[
                { key: "all",        label: `All (${matches.length})` },
                { key: "auto_match", label: `Auto Match (${result.summary.auto_match_count})` },
                { key: "review",     label: `Review (${result.summary.review_count})` },
                { key: "unmatched",  label: `Unmatched (${result.summary.unmatched_count})` },
              ].map((tab) => (
                <button key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition
                    ${filter === tab.key
                      ? "bg-blue-600 text-white shadow"
                      : "bg-white border border-gray-200 text-gray-600 hover:border-blue-300"}`}>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Match cards */}
            <div className="space-y-3">
              {filtered.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  No matches in this category.
                </div>
              ) : (
                filtered.map((match) => (
                  <MatchCard
                    key={match.match_id}
                    match={match}
                    onOverride={overrideMatch}
                  />
                ))
              )}
            </div>

            {/* Skipped items */}
            <SkippedSection items={result.skipped} />
          </div>
        )}
      </main>
    </div>
  );
}
