import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMatching } from "../hooks/useMatching";
import { DropZone } from "../components/upload/DropZone";
import { SummaryBar } from "../components/results/SummaryBar";
import { MatchCard } from "../components/results/MatchCard";
import { SkippedSection } from "../components/results/SkippedSection";

const C = {
  bg:        "#FFFFFF",
  bgAlt:     "#F7F5F0",
  text:      "#0F0F0F",
  textMid:   "#3A3530",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  gold:      "#8B6914",
  goldLight: "#F0E8D0",
};

/* ── SVG icons ───────────────────────────────────────────────────────────── */
const IcoBack = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 3L5 8l5 5"/>
  </svg>
);

const IcoPlay = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
    <path d="M5 3l9 5-9 5V3z"/>
  </svg>
);

const IcoLink = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
  </svg>
);

const IcoReset = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 7a5 5 0 1 0 1.5-3.5"/>
    <path d="M2 3v4h4"/>
  </svg>
);

/* ── Step bar ────────────────────────────────────────────────────────────── */
const STEPS   = [{ key:"idle", label:"Invoices" },{ key:"ledger_pending", label:"Ledger" },{ key:"ready", label:"Match" },{ key:"done", label:"Results" }];
const STEP_ORD= ["idle","ledger_pending","ready","matching","done"];

function StepBar({ step }) {
  const cur = STEP_ORD.indexOf(step);
  return (
    <div style={{ display:"flex", alignItems:"center" }}>
      {STEPS.map((s, i) => {
        const si    = STEP_ORD.indexOf(s.key);
        const done  = si < cur;
        const active= s.key === step || (step==="matching" && s.key==="ready");
        return (
          <div key={s.key} style={{ display:"flex", alignItems:"center" }}>
            <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:6 }}>
              <div style={{
                width:32, height:32, borderRadius:"50%",
                background: done ? C.text : active ? C.text : "transparent",
                border: `1.5px solid ${done||active ? C.text : C.border}`,
                color: done||active ? "#FFFFFF" : C.textMuted,
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:12, transition:"all 0.3s",
                fontFamily:"'Playfair Display', serif", fontWeight:600,
              }}>
                {done
                  ? <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="2.5 7.5 6 11 11.5 4"/></svg>
                  : i+1}
              </div>
              <span style={{
                fontSize:11, fontWeight:500, letterSpacing:"0.04em",
                color: active ? C.text : done ? C.textMid : C.textMuted,
                transition:"color 0.3s",
              }}>{s.label}</span>
            </div>
            {i < STEPS.length-1 && (
              <div style={{
                width:56, height:1, marginBottom:20, marginLeft:6, marginRight:6,
                background: done ? C.text : C.border,
                transition:"background 0.3s",
              }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Banners ─────────────────────────────────────────────────────────────── */
function ErrorBanner({ message, onDismiss }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", gap:12, marginBottom:20,
      background:"#FBE8E8", border:"1px solid #E8C4C4",
      borderRadius:6, padding:"11px 16px",
    }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#961010" strokeWidth="1.5" strokeLinecap="round">
        <circle cx="8" cy="8" r="6"/><path d="M8 5v4M8 10.5v.5"/>
      </svg>
      <span style={{ flex:1, color:"#961010", fontSize:13 }}>{message}</span>
      <button onClick={onDismiss} style={{ background:"none", border:"none", color:"#961010", cursor:"pointer", fontSize:16 }}>✕</button>
    </div>
  );
}

function ProgressBanner({ message }) {
  return (
    <div style={{
      display:"flex", alignItems:"center", gap:12, marginBottom:20,
      background:C.goldLight, border:`1px solid ${C.gold}33`,
      borderRadius:6, padding:"11px 16px",
    }}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke={C.gold} strokeWidth="1.5">
        <circle cx="8" cy="8" r="6" strokeDasharray="3 2" style={{ animation:"spin 1.2s linear infinite" }}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg);transform-origin:8px 8px}}`}</style>
      </svg>
      <span style={{ color:C.gold, fontSize:13 }}>{message}</span>
    </div>
  );
}

/* ── Upload section ──────────────────────────────────────────────────────── */
function UploadSection({ step, sessionId, busy, invoiceFiles, setInvoiceFiles, ledgerFiles, setLedgerFiles, onInvoiceUpload, onLedgerUpload, onMatch }) {

  const btnPrimary = (disabled) => ({
    width:"100%", marginTop:10, padding:"11px",
    background: disabled ? C.bgAlt : C.text,
    color: disabled ? C.textMuted : "#FFFFFF",
    border: `1px solid ${disabled ? C.border : C.text}`,
    borderRadius:6, fontSize:13, fontWeight:500,
    cursor: disabled ? "not-allowed" : "pointer",
    letterSpacing:"0.01em", transition:"opacity 0.15s",
    display:"flex", alignItems:"center", justifyContent:"center", gap:6,
  });

  return (
    <div>
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16, marginBottom:16 }}>
        {/* Invoice */}
        <div>
          <DropZone
            label="Invoice files"
            sublabel="Excel, CSV, PDF or images"
            accent={C.text}
            files={invoiceFiles}
            onFiles={setInvoiceFiles}
            disabled={busy || step==="ledger_pending" || step==="ready"}
            done={step==="ledger_pending" || step==="ready"}
          />
          {step==="idle" && (
            <button
              onClick={onInvoiceUpload}
              disabled={!invoiceFiles.length || busy}
              style={btnPrimary(!invoiceFiles.length || busy)}
              onMouseEnter={e => { if (invoiceFiles.length && !busy) e.currentTarget.style.opacity="0.85"; }}
              onMouseLeave={e => e.currentTarget.style.opacity="1"}>
              {busy ? "Extracting…" : "Upload invoices →"}
            </button>
          )}
        </div>

        {/* Ledger */}
        <div>
          <DropZone
            label="Ledger file"
            sublabel="Excel or CSV recommended"
            accent={C.text}
            files={ledgerFiles}
            onFiles={setLedgerFiles}
            disabled={busy || step==="idle" || step==="ready"}
            done={step==="ready"}
          />
          {step==="ledger_pending" && (
            <button
              onClick={onLedgerUpload}
              disabled={!ledgerFiles.length || busy}
              style={btnPrimary(!ledgerFiles.length || busy)}
              onMouseEnter={e => { if (ledgerFiles.length && !busy) e.currentTarget.style.opacity="0.85"; }}
              onMouseLeave={e => e.currentTarget.style.opacity="1"}>
              {busy ? "Extracting…" : "Upload ledger →"}
            </button>
          )}
        </div>
      </div>

      {step==="ready" && (
        <button onClick={onMatch} disabled={busy} style={{
          width:"100%", padding:"14px",
          background:C.text, color:"#FFFFFF",
          border:"none", borderRadius:6,
          fontSize:14, fontWeight:500, cursor:"pointer",
          display:"flex", alignItems:"center", justifyContent:"center", gap:8,
          letterSpacing:"0.01em", transition:"opacity 0.15s",
        }}
          onMouseEnter={e => e.currentTarget.style.opacity="0.85"}
          onMouseLeave={e => e.currentTarget.style.opacity="1"}>
          <IcoPlay /> Run matching pipeline
        </button>
      )}
    </div>
  );
}

/* ── Matching animation ──────────────────────────────────────────────────── */
function MatchingAnim() {
  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:"80px 0", gap:20 }}>
      <div style={{ position:"relative", width:48, height:48 }}>
        <svg viewBox="0 0 48 48" fill="none" style={{ position:"absolute", inset:0, animation:"spin 1.1s linear infinite" }}>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          <circle cx="24" cy="24" r="20" stroke={C.border} strokeWidth="2"/>
          <path d="M24 4a20 20 0 0 1 20 20" stroke={C.text} strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </div>
      <div style={{ textAlign:"center" }}>
        <div style={{ fontFamily:"'Playfair Display', serif", fontSize:18, fontWeight:600, color:C.text, marginBottom:6 }}>
          Running matching pipeline
        </div>
        <div style={{ fontSize:13, color:C.textMuted }}>
          Normalising · Scoring · Optimising · Classifying
        </div>
      </div>
      <div style={{ display:"flex", gap:0, alignItems:"center", marginTop:8 }}>
        {["Extract","Normalise","Score","Optimise","Classify"].map((s,i)=>(
          <div key={s} style={{ display:"flex", alignItems:"center" }}>
            <div style={{
              padding:"4px 12px", borderRadius:20,
              border:`1px solid ${C.border}`,
              background:C.bgAlt,
              color:C.textMuted, fontSize:11, fontWeight:500,
            }}>{s}</div>
            {i<4 && <div style={{ width:16, height:1, background:C.border }} />}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Filter tabs ─────────────────────────────────────────────────────────── */
function FilterTabs({ filter, setFilter, summary }) {
  const tabs = [
    { key:"all",        label:"All",        count:(summary?.auto_match_count||0)+(summary?.review_count||0)+(summary?.unmatched_count||0) },
    { key:"auto_match", label:"Auto match", count:summary?.auto_match_count||0 },
    { key:"review",     label:"Review",     count:summary?.review_count||0     },
    { key:"unmatched",  label:"Unmatched",  count:summary?.unmatched_count||0  },
  ];
  return (
    <div style={{ display:"flex", gap:6, marginBottom:16, flexWrap:"wrap" }}>
      {tabs.map(t => (
        <button key={t.key} onClick={() => setFilter(t.key)} style={{
          padding:"5px 14px", borderRadius:20,
          background: filter===t.key ? C.text : "transparent",
          color: filter===t.key ? "#FFFFFF" : C.textMuted,
          border: `1px solid ${filter===t.key ? C.text : C.border}`,
          fontSize:12, fontWeight:500, cursor:"pointer",
          display:"flex", alignItems:"center", gap:6,
          transition:"all 0.15s",
        }}>
          {t.label}
          <span style={{
            background: filter===t.key ? "rgba(255,255,255,0.2)" : C.bgAlt,
            color: filter===t.key ? "#FFFFFF" : C.textMuted,
            padding:"0 5px", borderRadius:10, fontSize:11,
          }}>{t.count}</span>
        </button>
      ))}
    </div>
  );
}

/* ── Main ────────────────────────────────────────────────────────────────── */
export function MatchPage() {
  const navigate = useNavigate();
  const { step, sessionId, result, error, progress,
    uploadInvoices, uploadLedger, runMatch, overrideMatch, reset } = useMatching();

  const [invoiceFiles, setInvoiceFiles] = useState([]);
  const [ledgerFiles,  setLedgerFiles]  = useState([]);
  const [filter,       setFilter]       = useState("all");

  const busy    = step==="uploading" || step==="matching";
  const matches = result?.matches ?? [];
  const filtered= filter==="all" ? matches : matches.filter(m=>(m.override_status||m.status)===filter);

  return (
    <div style={{ minHeight:"100vh", background:C.bg, color:C.text,
      fontFamily:"'Inter', -apple-system, sans-serif" }}>

      {/* ── Header ── */}
      <header style={{
        position:"sticky", top:0, zIndex:50,
        background:"rgba(255,255,255,0.96)",
        backdropFilter:"blur(10px)",
        borderBottom:`1px solid ${C.border}`,
        height:54, display:"flex", alignItems:"center",
        padding:"0 36px", justifyContent:"space-between",
      }}>
        <div style={{ display:"flex", alignItems:"center", gap:20 }}>
          <button onClick={() => navigate("/")} style={{
            display:"flex", alignItems:"center", gap:6,
            background:"none", border:"none",
            color:C.textMuted, fontSize:13, cursor:"pointer",
            padding:0, transition:"color 0.15s",
          }}
            onMouseEnter={e => e.currentTarget.style.color=C.text}
            onMouseLeave={e => e.currentTarget.style.color=C.textMuted}>
            <IcoBack /> Back
          </button>
          <div style={{ width:1, height:18, background:C.border }} />
          <div style={{ display:"flex", alignItems:"center", gap:7 }}>
            <IcoLink />
            <span style={{ fontFamily:"'Playfair Display', serif", fontWeight:600, fontSize:16 }}>matchIT</span>
          </div>
        </div>

        {step!=="idle" && (
          <button onClick={reset} style={{
            display:"flex", alignItems:"center", gap:6,
            background:"none", border:`1px solid ${C.border}`,
            color:C.textMuted, fontSize:12, fontWeight:500,
            padding:"5px 14px", borderRadius:6, cursor:"pointer",
            transition:"all 0.15s",
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor=C.text; e.currentTarget.style.color=C.text; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor=C.border; e.currentTarget.style.color=C.textMuted; }}>
            <IcoReset /> New session
          </button>
        )}
      </header>

      {/* ── Content ── */}
      <main style={{ maxWidth:860, margin:"0 auto", padding:"44px 36px" }}>

        {/* Step bar */}
        <div style={{ display:"flex", justifyContent:"center", marginBottom:52 }}>
          <StepBar step={step} />
        </div>

        {/* Banners */}
        {error    && <ErrorBanner    message={error}    onDismiss={reset} />}
        {progress && !error && <ProgressBanner message={progress} />}

        {/* Upload */}
        {step!=="done" && step!=="matching" && (
          <UploadSection
            step={step} sessionId={sessionId} busy={busy}
            invoiceFiles={invoiceFiles} setInvoiceFiles={setInvoiceFiles}
            ledgerFiles={ledgerFiles}   setLedgerFiles={setLedgerFiles}
            onInvoiceUpload={async () => { if (invoiceFiles.length) await uploadInvoices(invoiceFiles); }}
            onLedgerUpload={async ()  => { if (ledgerFiles.length && sessionId) await uploadLedger(sessionId, ledgerFiles); }}
            onMatch={async () => { if (sessionId) await runMatch(sessionId); }}
          />
        )}

        {/* Matching anim */}
        {step==="matching" && <MatchingAnim />}

        {/* Results */}
        {step==="done" && result && (
          <div>
            <SummaryBar summary={result.summary} sessionId={sessionId} />
            <div style={{ height:28 }} />
            <FilterTabs filter={filter} setFilter={setFilter} summary={result.summary} />
            <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
              {filtered.length===0
                ? <div style={{ textAlign:"center", padding:"60px 0", color:C.textMuted, fontSize:14 }}>No matches in this category.</div>
                : filtered.map(m => <MatchCard key={m.match_id} match={m} onOverride={overrideMatch} />)
              }
            </div>
            <div style={{ height:16 }} />
            <SkippedSection items={result.skipped} />
          </div>
        )}
      </main>
    </div>
  );
}