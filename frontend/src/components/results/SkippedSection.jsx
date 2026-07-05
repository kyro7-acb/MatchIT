import { useState } from "react";

const C = {
  bg:        "#FFFFFF",
  bgAlt:     "#F7F5F0",
  text:      "#0F0F0F",
  textMid:   "#3A3530",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  gold:      "#8B6914",
  goldBg:    "#F0E8D0",
};

function IcoChevron({ open }) {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      style={{ transition:"transform 0.2s", transform: open ? "rotate(180deg)" : "none" }}>
      <path d="M2 5l4.5 4.5L11 5"/>
    </svg>
  );
}

function IcoWarning() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
      stroke={C.gold} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 2L13 12H1L7 2z"/>
      <path d="M7 6v3M7 10.5v.5"/>
    </svg>
  );
}

export function SkippedSection({ items }) {
  const [open, setOpen] = useState(false);

  if (!items?.length) return null;

  return (
    <div style={{
      border:`1px solid ${C.border}`,
      borderRadius:8, overflow:"hidden",
      background:C.bg,
    }}>
      {/* header */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width:"100%", display:"flex",
          alignItems:"center", justifyContent:"space-between",
          padding:"14px 18px",
          background:"none", border:"none", cursor:"pointer",
          textAlign:"left",
          transition:"background 0.15s",
        }}
        onMouseEnter={e => e.currentTarget.style.background = C.bgAlt}
        onMouseLeave={e => e.currentTarget.style.background = "none"}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <IcoWarning />
          <div>
            <div style={{
              fontSize:13, fontWeight:500, color:C.text,
            }}>
              {items.length} skipped item{items.length > 1 ? "s" : ""}
            </div>
            <div style={{ fontSize:11, color:C.textMuted, marginTop:1 }}>
              Filtered out before matching — click to see reasons
            </div>
          </div>
        </div>
        <span style={{ color:C.textMuted }}>
          <IcoChevron open={open} />
        </span>
      </button>

      {/* items */}
      {open && (
        <div style={{ borderTop:`1px solid ${C.border}` }}>
          {items.map((item, i) => (
            <div key={i} style={{
              display:"flex", alignItems:"flex-start", gap:14,
              padding:"12px 18px",
              borderBottom: i < items.length - 1 ? `1px solid ${C.border}` : "none",
              background: i % 2 === 0 ? C.bg : C.bgAlt,
            }}>
              {/* type pill */}
              <span style={{
                fontSize:10, fontWeight:700,
                padding:"2px 7px", borderRadius:20,
                background: item.item_type === "invoice" ? "#E8F0FB" : C.goldBg,
                color:       item.item_type === "invoice" ? "#1A3A7A" : C.gold,
                letterSpacing:"0.06em", textTransform:"uppercase",
                flexShrink:0, marginTop:1,
              }}>
                {item.item_type === "invoice" ? "INV" : "LED"}
              </span>

              {/* content */}
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{
                  fontFamily:"monospace", fontSize:13,
                  fontWeight:500, color:C.text,
                  marginBottom:3,
                }}>
                  {item.item_ref || "—"}
                </div>
                <div style={{ fontSize:12, color:C.textMuted, lineHeight:1.5 }}>
                  {item.reason}
                </div>
                {item.detail && Object.keys(item.detail).length > 0 && (
                  <div style={{
                    marginTop:4, fontSize:11,
                    fontFamily:"monospace", color:C.textMuted,
                  }}>
                    {Object.entries(item.detail).map(([k,v]) =>
                      `${k}: ${v}`
                    ).join(" · ")}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}