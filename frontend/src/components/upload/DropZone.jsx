import { useRef, useState } from "react";

const C = {
  bg:        "#FFFFFF",
  bgAlt:     "#F7F5F0",
  text:      "#0F0F0F",
  textMuted: "#6B6560",
  border:    "#E8E4DC",
  borderMid: "#C8C4BC",
  green:     "#2A6016",
  greenBg:   "#EEFBE8",
};

const ACCEPT = ".jpg,.jpeg,.png,.pdf,.xlsx,.xls,.csv";

function IcoCheck() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none"
      stroke={C.green} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="2.5 7.5 6 11 11.5 4.5"/>
    </svg>
  );
}

function IcoFile() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7.5 1.5H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V5l-3.5-3.5z"/>
      <polyline points="7.5 1.5 7.5 5 11 5"/>
    </svg>
  );
}

export function DropZone({ label, sublabel, files = [], onFiles, disabled, done, accent }) {
  const inputRef = useRef(null);
  const [drag,   setDrag]  = useState(false);

  const handle = (incoming) => {
    if (disabled) return;
    const arr = Array.from(incoming).filter(f => {
      const ext = "." + f.name.split(".").pop().toLowerCase();
      return ACCEPT.includes(ext);
    });
    if (arr.length) onFiles(arr);
  };

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={e  => { e.preventDefault(); if (!disabled) setDrag(true);  }}
      onDragLeave={() => setDrag(false)}
      onDrop={e      => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files); }}
      style={{
        border:`1px ${drag ? "solid" : "dashed"} ${
          done ? C.borderMid :
          drag ? C.text      : C.border
        }`,
        borderRadius:8,
        padding:"22px 20px",
        cursor: disabled ? "not-allowed" : "pointer",
        background: done ? C.bgAlt : drag ? "#F7F5F0" : C.bg,
        opacity: disabled && !done ? 0.45 : 1,
        transition:"all 0.15s",
        userSelect:"none",
      }}>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        style={{ display:"none" }}
        onChange={e => handle(e.target.files)}
        disabled={disabled}
      />

      <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:8, textAlign:"center" }}>
        {/* status icon */}
        {done ? (
          <div style={{
            width:36, height:36, borderRadius:"50%",
            background:C.greenBg,
            display:"flex", alignItems:"center", justifyContent:"center",
          }}>
            <IcoCheck />
          </div>
        ) : (
          <div style={{
            width:36, height:36, borderRadius:"50%",
            background:C.bgAlt, border:`1px solid ${C.border}`,
            display:"flex", alignItems:"center", justifyContent:"center",
          }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"
              stroke={C.textMuted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 11V5M5 8l3-3 3 3"/>
              <path d="M3 13h10"/>
            </svg>
          </div>
        )}

        {/* label */}
        <div>
          <div style={{
            fontSize:13, fontWeight:500,
            color: done ? C.green : C.text,
          }}>
            {done ? "Uploaded" : label}
          </div>
          <div style={{ fontSize:11, color:C.textMuted, marginTop:2 }}>
            {done ? `${files.length} file${files.length !== 1 ? "s" : ""} ready` : sublabel}
          </div>
        </div>

        {/* file chips */}
        {files.length > 0 && (
          <div style={{ width:"100%", display:"flex", flexDirection:"column", gap:4, marginTop:4 }}>
            {files.map((f, i) => (
              <div key={i} style={{
                display:"flex", alignItems:"center", gap:7,
                background:C.bg,
                border:`1px solid ${C.border}`,
                borderRadius:5, padding:"5px 10px",
                fontSize:11, color:C.textMuted,
                textAlign:"left",
              }}>
                <span style={{ color:C.textMuted, flexShrink:0 }}><IcoFile /></span>
                <span style={{
                  flex:1, overflow:"hidden",
                  textOverflow:"ellipsis", whiteSpace:"nowrap",
                  color:C.text,
                }}>
                  {f.name}
                </span>
                <span style={{ flexShrink:0, fontFamily:"monospace" }}>
                  {(f.size / 1024).toFixed(0)} KB
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}