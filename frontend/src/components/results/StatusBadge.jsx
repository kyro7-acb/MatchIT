const CONF = {
  auto_match: { label:"Auto match",  bg:"#EEFBE8", text:"#2A6016", dot:"#2A6016" },
  review:     { label:"Review",      bg:"#F0E8D0", text:"#7A4F0A", dot:"#8B6914" },
  unmatched:  { label:"Unmatched",   bg:"#FBE8E8", text:"#961010", dot:"#961010" },
  confirmed:  { label:"Confirmed",   bg:"#E8F0FB", text:"#1A3A7A", dot:"#2A5ABD" },
  rejected:   { label:"Rejected",    bg:"#F0EEE8", text:"#4A4540", dot:"#6B6560" },
};

export function StatusBadge({ status, overridden = false }) {
  const c = CONF[status] || CONF.unmatched;
  return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap:6,
      padding:"3px 10px", borderRadius:20,
      background:c.bg, color:c.text,
      fontSize:11, fontWeight:600,
      letterSpacing:"0.04em",
      flexShrink:0,
    }}>
      <span style={{
        width:5, height:5, borderRadius:"50%",
        background:c.dot, flexShrink:0,
      }} />
      {c.label}
      {overridden && (
        <span style={{ opacity:0.55, fontWeight:400, fontSize:10 }}>
          (overridden)
        </span>
      )}
    </span>
  );
}