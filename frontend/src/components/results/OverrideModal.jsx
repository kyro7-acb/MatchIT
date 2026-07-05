import { useState } from "react";

const C = {
  bg:        "#FFFFFF",
  bgAlt:     "#F7F5F0",
  text:      "#0F0F0F",
  textMid:   "#3A3530",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  borderMid: "#C8C4BC",
};

const OPTIONS = [
  { value:"confirmed", label:"Confirm this match",   sub:"Mark as verified and approved" },
  { value:"rejected",  label:"Reject this match",    sub:"No valid correspondence exists" },
  { value:"review",    label:"Keep under review",    sub:"Flag for further investigation" },
];

export function OverrideModal({ match, onConfirm, onClose }) {
  const [status, setStatus] = useState("confirmed");
  const [note,   setNote]   = useState("");
  const [busy,   setBusy]   = useState(false);

  const submit = async () => {
    setBusy(true);
    await onConfirm(match.match_id, status, note);
    setBusy(false);
    onClose();
  };

  return (
    /* faux viewport — fixed won't work in iframe */
    <div style={{
      position:"absolute", inset:0, zIndex:200,
      background:"rgba(15,12,8,0.45)",
      display:"flex", alignItems:"center", justifyContent:"center",
      padding:24,
      minHeight:400,
    }}>
      <div style={{
        background:C.bg,
        border:`1px solid ${C.border}`,
        borderRadius:10,
        width:"100%", maxWidth:420,
        overflow:"hidden",
      }}>
        {/* header */}
        <div style={{
          padding:"20px 24px 16px",
          borderBottom:`1px solid ${C.border}`,
        }}>
          <div style={{
            fontFamily:"'Playfair Display', serif",
            fontSize:18, fontWeight:700,
            color:C.text, letterSpacing:"-0.02em",
            marginBottom:6,
          }}>
            Override decision
          </div>
          <div style={{ fontSize:12, color:C.textMuted }}>
            <span style={{ fontFamily:"monospace" }}>
              {match.invoice?.invoice_number || "—"}
            </span>
            {" "}↔{" "}
            <span style={{ fontFamily:"monospace" }}>
              {match.ledger_entry?.reference || "—"}
            </span>
          </div>
        </div>

        {/* options */}
        <div style={{ padding:"16px 24px", display:"flex", flexDirection:"column", gap:8 }}>
          {OPTIONS.map(opt => (
            <label key={opt.value} style={{
              display:"flex", alignItems:"center", gap:14,
              padding:"12px 14px",
              border:`1px solid ${status === opt.value ? C.text : C.border}`,
              borderRadius:6,
              cursor:"pointer",
              background: status === opt.value ? C.bgAlt : C.bg,
              transition:"all 0.15s",
            }}>
              {/* custom radio */}
              <div style={{
                width:16, height:16, borderRadius:"50%",
                border:`1.5px solid ${status === opt.value ? C.text : C.borderMid}`,
                background: status === opt.value ? C.text : "transparent",
                flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center",
                transition:"all 0.15s",
              }}>
                {status === opt.value && (
                  <div style={{ width:5, height:5, borderRadius:"50%", background:"#FFFFFF" }} />
                )}
              </div>
              <input
                type="radio" name="override-status" value={opt.value}
                checked={status === opt.value}
                onChange={() => setStatus(opt.value)}
                style={{ display:"none" }}
              />
              <div>
                <div style={{ fontSize:13, fontWeight:500, color:C.text }}>{opt.label}</div>
                <div style={{ fontSize:11, color:C.textMuted, marginTop:2 }}>{opt.sub}</div>
              </div>
            </label>
          ))}
        </div>

        {/* note */}
        <div style={{ padding:"0 24px 16px" }}>
          <textarea
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Optional note — reason for this override…"
            rows={2}
            style={{
              width:"100%", resize:"none",
              border:`1px solid ${C.border}`,
              borderRadius:6, padding:"10px 12px",
              fontSize:13, color:C.text,
              background:C.bg,
              outline:"none",
              fontFamily:"inherit",
              transition:"border-color 0.15s",
            }}
            onFocus={e => e.target.style.borderColor = C.text}
            onBlur={e  => e.target.style.borderColor = C.border}
          />
        </div>

        {/* actions */}
        <div style={{
          display:"flex", gap:8, padding:"14px 24px",
          borderTop:`1px solid ${C.border}`,
        }}>
          <button onClick={onClose} style={{
            flex:1, padding:"10px",
            background:C.bg,
            border:`1px solid ${C.border}`,
            borderRadius:6, fontSize:13, fontWeight:500,
            color:C.textMid, cursor:"pointer",
            transition:"border-color 0.15s",
          }}
            onMouseEnter={e => e.currentTarget.style.borderColor = C.text}
            onMouseLeave={e => e.currentTarget.style.borderColor = C.border}>
            Cancel
          </button>
          <button onClick={submit} disabled={busy} style={{
            flex:1, padding:"10px",
            background: busy ? "#888" : C.text,
            border:"none",
            borderRadius:6, fontSize:13, fontWeight:500,
            color:"#FFFFFF", cursor: busy ? "not-allowed" : "pointer",
            transition:"opacity 0.15s",
            letterSpacing:"0.01em",
          }}
            onMouseEnter={e => { if (!busy) e.currentTarget.style.opacity="0.85"; }}
            onMouseLeave={e => e.currentTarget.style.opacity="1"}>
            {busy ? "Saving…" : "Save override"}
          </button>
        </div>
      </div>
    </div>
  );
}