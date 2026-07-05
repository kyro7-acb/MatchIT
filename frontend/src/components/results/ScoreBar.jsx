const C = {
  text:      "#0F0F0F",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  gold:      "#8B6914",
  goldLight: "#F0E8D0",
  green:     "#2A6016",
  greenBg:   "#EEFBE8",
  amber:     "#7A4F0A",
  amberBg:   "#F0E8D0",
  red:       "#961010",
  redBg:     "#FBE8E8",
};

export function ScoreBar({ score, size = "md" }) {
  const pct  = Math.round(score * 100);
  const isHigh= pct >= 90;
  const isMid = pct >= 70 && pct < 90;
  const color = isHigh ? C.green : isMid ? C.gold : C.red;
  const h     = size === "sm" ? 3 : 4;

  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, width:"100%" }}>
      <div style={{
        flex:1, background:C.border,
        borderRadius:2, height:h, overflow:"hidden",
      }}>
        <div style={{
          height:"100%", borderRadius:2,
          background:color,
          width:`${pct}%`,
          transition:"width 0.6s cubic-bezier(.2,1,.3,1)",
        }} />
      </div>
      <span style={{
        fontFamily:"'Playfair Display', serif",
        fontWeight:600,
        fontSize: size === "sm" ? 11 : 13,
        color,
        flexShrink:0,
        minWidth:36,
        textAlign:"right",
        letterSpacing:"-0.01em",
      }}>
        {score.toFixed(4)}
      </span>
    </div>
  );
}