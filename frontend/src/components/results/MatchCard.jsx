import { useState } from "react";
import { ScoreBar }     from "./ScoreBar";
import { StatusBadge }  from "./StatusBadge";
import { ExplainPanel } from "./ExplainPanel";
import { OverrideModal } from "./OverrideModal";

const C = {
  bg:        "#FFFFFF",
  bgAlt:     "#F7F5F0",
  text:      "#0F0F0F",
  textMid:   "#3A3530",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  borderMid: "#C8C4BC",
  gold:      "#8B6914",
};

/* ── tiny helpers ── */
const IcoChevron = ({ open }) => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    style={{ transition:"transform 0.2s", transform: open ? "rotate(90deg)" : "rotate(0)" }}>
    <path d="M5 3l4 4-4 4"/>
  </svg>
);

const IcoPencil = () => (
  <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 2l2 2-7 7H2v-2L9 2z"/>
  </svg>
);

/* field row inside the side-by-side panel */
function FieldRow({ label, value, highlight }) {
  return (
    <div style={{ marginBottom:8 }}>
      <div style={{ fontSize:10, color:C.textMuted, letterSpacing:"0.06em",
        textTransform:"uppercase", marginBottom:2 }}>
        {label}
      </div>
      <div style={{
        fontSize:12, fontWeight:500,
        fontFamily:"monospace",
        color: highlight ? C.gold : C.textMid,
        background: highlight ? "#F0E8D0" : "transparent",
        padding: highlight ? "1px 5px" : 0,
        borderRadius: highlight ? 3 : 0,
        display:"inline-block",
        maxWidth:"100%",
        overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
      }}>
        {value || <span style={{ color:C.border, fontStyle:"italic" }}>—</span>}
      </div>
    </div>
  );
}

/* side panel (invoice or ledger) */
function SidePanel({ title, accent, fields, highlight }) {
  return (
    <div style={{
      flex:1, minWidth:0,
      border:`1px solid ${C.border}`,
      borderRadius:6, padding:"14px 16px",
      background:C.bgAlt,
    }}>
      <div style={{
        fontSize:10, fontWeight:600,
        color:accent, letterSpacing:"0.1em",
        textTransform:"uppercase", marginBottom:12,
      }}>
        {title}
      </div>
      {fields.map(([label, value, hl]) => (
        <FieldRow key={label} label={label} value={value} highlight={hl && highlight[label]} />
      ))}
    </div>
  );
}

/* ── main card ── */
export function MatchCard({ match, onOverride }) {
  const [open,        setOpen]        = useState(false);
  const [showExplain, setShowExplain] = useState(false);
  const [showOverride,setShowOverride]= useState(false);

  const {
    invoice:    inv,
    ledger_entry: led,
    score, status,
    field_breakdown: bd,
    is_overridden, override_status, override_note,
    match_id,
  } = match;

  const displayStatus = override_status || status;

  const borderColor =
    displayStatus === "auto_match" ? "#C8E4C0" :
    displayStatus === "review"     ? "#E4D8B0" :
                                     "#E4C0C0";

  /* which fields are "highlighted" (score ≥ 0.9) */
  const hl = {
    "Invoice number": bd?.invoice_number?.score >= 0.9,
    "Vendor":         bd?.vendor?.score         >= 0.9,
    "Date":           bd?.date?.score           >= 0.9,
    "Amount":         bd?.amount?.score         >= 0.9,
  };

  return (
    <>
      <div style={{
        background:C.bg,
        border:`1px solid ${borderColor}`,
        borderRadius:8,
        overflow: showOverride ? "visible" : "hidden",
        position:"relative",
        transition:"box-shadow 0.15s",
      }}
        onMouseEnter={e => e.currentTarget.style.boxShadow="0 1px 8px rgba(15,12,8,0.06)"}
        onMouseLeave={e => e.currentTarget.style.boxShadow="none"}>

        {/* ── collapsed header ── */}
        <div
          onClick={() => setOpen(o => !o)}
          style={{
            display:"flex", alignItems:"center", gap:12,
            padding:"14px 16px",
            cursor:"pointer", userSelect:"none",
          }}>

          {/* chevron */}
          <span style={{ color:C.textMuted, flexShrink:0 }}>
            <IcoChevron open={open} />
          </span>

          {/* ref pair */}
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{
              display:"flex", alignItems:"center", gap:8,
              fontFamily:"monospace", fontSize:13, fontWeight:600,
              color:C.text, flexWrap:"wrap",
            }}>
              <span>{inv?.invoice_number || "No number"}</span>
              <span style={{ color:C.border, fontFamily:"sans-serif", fontWeight:400 }}>↔</span>
              <span>{led?.reference || "No reference"}</span>
            </div>
            <div style={{
              fontSize:12, color:C.textMuted, marginTop:3,
              overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
            }}>
              {inv?.vendor_name || "—"} · {inv?.date || "—"}
            </div>
          </div>

          {/* score bar */}
          <div style={{ width:140, flexShrink:0 }}>
            <ScoreBar score={score} />
          </div>

          {/* badge */}
          <StatusBadge status={displayStatus} overridden={is_overridden} />
        </div>

        {/* ── expanded body ── */}
        {open && (
          <div style={{ borderTop:`1px solid ${C.border}`, padding:"16px" }}>

            {/* side-by-side */}
            <div style={{ display:"flex", gap:10, marginBottom:16 }}>
              <SidePanel
                title="Invoice"
                accent="#1A4A7A"
                highlight={hl}
                fields={[
                  ["Invoice number", inv?.invoice_number, true],
                  ["Vendor",         inv?.vendor_name,    true],
                  ["Date",           inv?.date,           true],
                  ["Amount",         inv?.amount,         true],
                  ["Source",         inv?.source_file,    false],
                ]}
              />
              <SidePanel
                title="Ledger entry"
                accent={C.gold}
                highlight={hl}
                fields={[
                  ["Reference", led?.reference, true],
                  ["Vendor",    led?.vendor,    true],
                  ["Date",      led?.date,      true],
                  ["Debit",     led?.debit,     true],
                  ["Source",    led?.source_file, false],
                ]}
              />
            </div>

            {/* override note */}
            {is_overridden && override_note && (
              <div style={{
                display:"flex", gap:10, alignItems:"flex-start",
                background:"#F7F5F0", border:`1px solid ${C.border}`,
                borderRadius:6, padding:"10px 12px",
                marginBottom:12,
              }}>
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
                  stroke={C.textMuted} strokeWidth="1.5" strokeLinecap="round" style={{ marginTop:1, flexShrink:0 }}>
                  <circle cx="6.5" cy="6.5" r="5"/><path d="M6.5 4.5v3M6.5 8.5v.5"/>
                </svg>
                <div style={{ fontSize:12, color:C.textMuted }}>
                  <span style={{ fontWeight:500, color:C.text }}>Override note: </span>
                  {override_note}
                </div>
              </div>
            )}

            {/* explain toggle */}
            <button
              onClick={() => setShowExplain(s => !s)}
              style={{
                background:"none", border:"none", padding:0,
                fontSize:12, color:C.textMuted, cursor:"pointer",
                display:"flex", alignItems:"center", gap:5,
                marginBottom: showExplain ? 12 : 0,
                transition:"color 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.color = C.text}
              onMouseLeave={e => e.currentTarget.style.color = C.textMuted}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                style={{ transition:"transform 0.2s", transform: showExplain ? "rotate(180deg)" : "none" }}>
                <path d="M2 4l4 4 4-4"/>
              </svg>
              {showExplain ? "Hide" : "Show"} score breakdown
            </button>

            {showExplain && bd && (
              <ExplainPanel breakdown={bd} totalScore={score} />
            )}

            {/* actions */}
            <div style={{ display:"flex", justifyContent:"flex-end", marginTop:14 }}>
              <button
                onClick={() => setShowOverride(true)}
                style={{
                  display:"flex", alignItems:"center", gap:6,
                  padding:"7px 14px",
                  background:"none",
                  border:`1px solid ${C.border}`,
                  borderRadius:6, fontSize:12, fontWeight:500,
                  color:C.textMid, cursor:"pointer",
                  transition:"all 0.15s",
                  letterSpacing:"0.01em",
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = C.text; e.currentTarget.style.color = C.text; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.color = C.textMid; }}>
                <IcoPencil /> Override decision
              </button>
            </div>
          </div>
        )}
      </div>

      {showOverride && (
        <OverrideModal
          match={match}
          onConfirm={onOverride}
          onClose={() => setShowOverride(false)}
        />
      )}
    </>
  );
}