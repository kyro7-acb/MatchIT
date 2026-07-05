import { ScoreBar } from "./ScoreBar";

const C = {
  bg:        "#FFFFFF",
  bgAlt:     "#F7F5F0",
  text:      "#0F0F0F",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  gold:      "#8B6914",
};

const FIELDS = {
  invoice_number: { label:"Invoice number", weight:"40%" },
  vendor:         { label:"Vendor name",    weight:"25%" },
  date:           { label:"Date",           weight:"20%" },
  amount:         { label:"Amount",         weight:"15%" },
};

export function ExplainPanel({ breakdown, totalScore }) {
  return (
    <div style={{
      background:C.bgAlt,
      border:`1px solid ${C.border}`,
      borderRadius:6,
      overflow:"hidden",
    }}>
      {/* header */}
      <div style={{
        display:"flex", alignItems:"center", justifyContent:"space-between",
        padding:"10px 16px",
        borderBottom:`1px solid ${C.border}`,
      }}>
        <span style={{
          fontSize:11, fontWeight:500,
          color:C.textMuted,
          letterSpacing:"0.1em", textTransform:"uppercase",
        }}>
          Score breakdown
        </span>
        <span style={{
          fontFamily:"'Playfair Display', serif",
          fontSize:14, fontWeight:700,
          color:C.text, letterSpacing:"-0.01em",
        }}>
          {totalScore.toFixed(4)}
        </span>
      </div>

      {/* rows */}
      {Object.entries(breakdown).map(([field, data], i) => {
        const meta   = FIELDS[field] || { label:field, weight:"" };
        const isLast = i === Object.entries(breakdown).length - 1;
        const match  = data.score >= 0.9;
        const partial= data.score >= 0.6 && data.score < 0.9;
        const valBg  = match ? "#EEFBE8" : partial ? "#F0E8D0" : "#FBE8E8";
        const valCol = match ? "#2A6016" : partial ? "#7A4F0A" : "#961010";

        return (
          <div key={field} style={{
            display:"grid",
            gridTemplateColumns:"120px 1fr 120px 64px",
            gap:12, alignItems:"center",
            padding:"10px 16px",
            borderBottom: isLast ? "none" : `1px solid ${C.border}`,
            background:C.bg,
          }}>
            {/* field name + weight */}
            <div>
              <div style={{ fontSize:12, fontWeight:500, color:C.text }}>{meta.label}</div>
              <div style={{ fontSize:10, color:C.textMuted, marginTop:1 }}>weight {meta.weight}</div>
            </div>

            {/* values */}
            <div style={{ display:"flex", flexDirection:"column", gap:3, minWidth:0 }}>
              <span style={{
                fontSize:11, fontFamily:"monospace",
                padding:"2px 6px", borderRadius:3,
                background:valBg, color:valCol,
                display:"inline-block", maxWidth:"100%",
                overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
              }}>
                ↑ {data.invoice_value || "—"}
              </span>
              <span style={{
                fontSize:11, fontFamily:"monospace",
                padding:"2px 6px", borderRadius:3,
                background:valBg, color:valCol,
                display:"inline-block", maxWidth:"100%",
                overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
              }}>
                ↓ {data.ledger_value || "—"}
              </span>
            </div>

            {/* score bar */}
            <ScoreBar score={data.score} size="sm" />

            {/* contribution */}
            <div style={{ textAlign:"right" }}>
              <div style={{ fontSize:10, color:C.textMuted, marginBottom:1 }}>contrib.</div>
              <div style={{
                fontFamily:"'Playfair Display', serif",
                fontSize:13, fontWeight:700,
                color:C.text,
              }}>
                +{data.contribution.toFixed(3)}
              </div>
            </div>
          </div>
        );
      })}

      {/* legend */}
      <div style={{
        display:"flex", gap:16, padding:"8px 16px",
        borderTop:`1px solid ${C.border}`,
        background:C.bgAlt,
      }}>
        {[
          { bg:"#EEFBE8", text:"#2A6016", label:"≥ 0.90 strong" },
          { bg:"#F0E8D0", text:"#7A4F0A", label:"0.60–0.89 partial" },
          { bg:"#FBE8E8", text:"#961010", label:"< 0.60 weak" },
        ].map(({ bg, text, label }) => (
          <div key={label} style={{ display:"flex", alignItems:"center", gap:5 }}>
            <div style={{ width:8, height:8, borderRadius:2, background:bg, border:`1px solid ${text}44` }} />
            <span style={{ fontSize:10, color:C.textMuted }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}