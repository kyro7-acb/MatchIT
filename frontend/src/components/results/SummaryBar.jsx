import { api } from "../../utils/api";

const C = {
  bg:        "#FFFFFF",
  bgAlt:     "#F7F5F0",
  text:      "#0F0F0F",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  green:     "#2A6016",
  greenBg:   "#EEFBE8",
  gold:      "#8B6914",
  goldBg:    "#F0E8D0",
  red:       "#961010",
  redBg:     "#FBE8E8",
};

function Stat({ value, label, color, bg }) {
  return (
    <div style={{
      display:"flex", flexDirection:"column", alignItems:"center",
      padding:"16px 24px",
      background:bg, borderRadius:6,
      border:`1px solid ${color}22`,
      minWidth:80,
    }}>
      <span style={{
        fontFamily:"'Playfair Display', serif",
        fontSize:32, fontWeight:700,
        color, letterSpacing:"-0.03em", lineHeight:1,
      }}>
        {value}
      </span>
      <span style={{ fontSize:11, color:C.textMuted, marginTop:5, letterSpacing:"0.04em" }}>
        {label}
      </span>
    </div>
  );
}

function IcoDownload() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6.5 2v7M3 7l3.5 3.5L10 7"/><path d="M1 11h11"/>
    </svg>
  );
}

export function SummaryBar({ summary, sessionId }) {
  const total = summary.total_invoices || 0;
  const auto  = summary.auto_match_count || 0;
  const rev   = summary.review_count || 0;
  const unm   = summary.unmatched_count || 0;
  const skip  = summary.skipped_count || 0;

  return (
    <div style={{
      background:C.bg,
      border:`1px solid ${C.border}`,
      borderRadius:8, padding:"20px 24px",
    }}>
      {/* title row */}
      <div style={{
        display:"flex", alignItems:"center", justifyContent:"space-between",
        marginBottom:18,
      }}>
        <div>
          <div style={{
            fontFamily:"'Playfair Display', serif",
            fontSize:17, fontWeight:700,
            color:C.text, letterSpacing:"-0.02em",
          }}>
            Reconciliation complete
          </div>
          <div style={{ fontSize:12, color:C.textMuted, marginTop:2 }}>
            {total} invoice{total !== 1 ? "s" : ""} · {summary.total_ledger || 0} ledger entries
          </div>
        </div>

        {/* export buttons */}
        <div style={{ display:"flex", gap:8 }}>
          <a href={api.exportUrl(sessionId, "csv")} target="_blank" rel="noreferrer"
            style={{
              display:"flex", alignItems:"center", gap:6,
              padding:"7px 14px",
              background:C.bg,
              border:`1px solid ${C.border}`,
              borderRadius:6, fontSize:12, fontWeight:500,
              color:C.textMuted, textDecoration:"none",
              transition:"all 0.15s",
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor=C.text; e.currentTarget.style.color=C.text; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor=C.border; e.currentTarget.style.color=C.textMuted; }}>
            <IcoDownload /> CSV
          </a>
          <a href={api.exportUrl(sessionId, "json")} target="_blank" rel="noreferrer"
            style={{
              display:"flex", alignItems:"center", gap:6,
              padding:"7px 14px",
              background:C.text,
              border:`1px solid ${C.text}`,
              borderRadius:6, fontSize:12, fontWeight:500,
              color:"#FFFFFF", textDecoration:"none",
              transition:"opacity 0.15s",
            }}
            onMouseEnter={e => e.currentTarget.style.opacity="0.85"}
            onMouseLeave={e => e.currentTarget.style.opacity="1"}>
            <IcoDownload /> JSON
          </a>
        </div>
      </div>

      {/* stat tiles */}
      <div style={{ display:"flex", gap:10, flexWrap:"wrap", marginBottom:18 }}>
        <Stat value={auto}  label="Auto match" color={C.green} bg={C.greenBg} />
        <Stat value={rev}   label="Review"      color={C.gold}  bg={C.goldBg}  />
        <Stat value={unm}   label="Unmatched"   color={C.red}   bg={C.redBg}   />
        <Stat value={skip}  label="Skipped"     color={C.textMuted} bg={C.bgAlt} />
      </div>

      {/* stacked progress bar */}
      {total > 0 && (
        <div>
          <div style={{
            display:"flex", height:5,
            borderRadius:3, overflow:"hidden",
            background:C.bgAlt,
          }}>
            <div style={{
              width:`${(auto / total) * 100}%`,
              background:C.green,
              transition:"width 0.6s cubic-bezier(.2,1,.3,1)",
            }} />
            <div style={{
              width:`${(rev / total) * 100}%`,
              background:C.gold,
              transition:"width 0.6s cubic-bezier(.2,1,.3,1) 0.05s",
            }} />
            <div style={{
              width:`${(unm / total) * 100}%`,
              background:C.red,
              transition:"width 0.6s cubic-bezier(.2,1,.3,1) 0.1s",
            }} />
          </div>
          <div style={{
            display:"flex", gap:16, marginTop:8,
          }}>
            {[
              { color:C.green,     label:`${Math.round((auto/total)*100)}% auto-matched` },
              { color:C.gold,      label:`${Math.round((rev/total)*100)}% review` },
              { color:C.red,       label:`${Math.round((unm/total)*100)}% unmatched` },
            ].map(({ color, label }) => (
              <div key={label} style={{ display:"flex", alignItems:"center", gap:5 }}>
                <div style={{ width:6, height:6, borderRadius:"50%", background:color }} />
                <span style={{ fontSize:11, color:C.textMuted }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}