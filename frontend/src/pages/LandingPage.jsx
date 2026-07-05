import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

/* ─── colour tokens ──────────────────────────────────────────────────────── */
const C = {
  bg:         "#FFFFFF",
  bgAlt:      "#F7F5F0",
  bgDark:     "#0F0F0F",
  text:       "#0F0F0F",
  textMid:    "#3A3530",
  textMuted:  "#6B6560",
  border:     "#E8E4DC",
  borderMid:  "#C8C4BC",
  gold:       "#8B6914",
  goldLight:  "#F0E8D0",
};

/* ─── SVG icons (black, outline) ─────────────────────────────────────────── */
const IcoLink = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
  </svg>
);

const IcoArrowRight = ({ size = 18 }) => (
  <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9h12M10 4l5 5-5 5"/>
  </svg>
);

const IcoArrowDown = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 3v10M3 9l5 5 5-5"/>
  </svg>
);

const IcoFile = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z"/>
    <polyline points="13 2 13 7 18 7"/>
    <line x1="7" y1="12" x2="15" y2="12"/>
    <line x1="7" y1="16" x2="11" y2="16"/>
  </svg>
);

const IcoGrid = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1"/>
    <rect x="12" y="3" width="7" height="7" rx="1"/>
    <rect x="3" y="12" width="7" height="7" rx="1"/>
    <rect x="12" y="12" width="7" height="7" rx="1"/>
  </svg>
);

const IcoTarget = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="9"/>
    <circle cx="11" cy="11" r="5"/>
    <circle cx="11" cy="11" r="1" fill="currentColor"/>
  </svg>
);

const IcoEye = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 11S4 4 11 4s10 7 10 7-3 7-10 7S1 11 1 11z"/>
    <circle cx="11" cy="11" r="3"/>
  </svg>
);

const IcoCheck = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={C.gold} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="2.5 8.5 6.5 12.5 13.5 4.5"/>
  </svg>
);

const IcoDownload = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M11 3v12M5 10l6 6 6-6"/>
    <path d="M3 18h16"/>
  </svg>
);

/* ─── Scroll-reveal wrapper ──────────────────────────────────────────────── */
function Reveal({ children, delay = 0, style = {} }) {
  const ref = useRef(null);
  const [v, setV] = useState(false);
  useEffect(() => {
    const o = new IntersectionObserver(([e]) => { if (e.isIntersecting) setV(true); }, { threshold: 0.12 });
    if (ref.current) o.observe(ref.current);
    return () => o.disconnect();
  }, []);
  return (
    <div ref={ref} style={{
      opacity: v ? 1 : 0,
      transform: v ? "none" : "translateY(18px)",
      transition: `opacity 0.6s ease ${delay}ms, transform 0.6s cubic-bezier(.2,1,.3,1) ${delay}ms`,
      ...style,
    }}>
      {children}
    </div>
  );
}

/* ─── Hero split-document visual ─────────────────────────────────────────── */
function HeroDoc() {
  const [matched, setMatched] = useState(false);
  useEffect(() => { const t = setTimeout(() => setMatched(true), 900); return () => clearTimeout(t); }, []);

  const docStyle = {
    background: C.bg,
    border: `1px solid ${C.border}`,
    borderRadius: 6,
    padding: "20px 22px",
    width: 190,
    fontFamily: "'Inter', sans-serif",
  };
  const labelStyle = { fontSize: 9, color: C.textMuted, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 };
  const rowStyle   = { marginBottom: 7 };
  const keyStyle   = { fontSize: 10, color: C.textMuted, marginBottom: 1 };
  const valStyle   = (highlight) => ({
    fontSize: 12, fontWeight: 500, color: highlight ? C.gold : C.text,
    background: highlight ? C.goldLight : "none",
    padding: highlight ? "1px 5px" : 0,
    borderRadius: highlight ? 3 : 0,
    display: "inline-block",
  });

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, userSelect: "none" }}>
      {/* Invoice */}
      <div style={{ ...docStyle, opacity: matched ? 1 : 0, transform: matched ? "none" : "translateX(-16px)", transition: "all 0.6s cubic-bezier(.2,1,.3,1)" }}>
        <div style={labelStyle}>Invoice</div>
        {[["Number","INV-2024-047",true],["Vendor","Himalayan Ltd",true],["Date","15 Jan 2024",false],["Amount","₹45,000",false]].map(([k,v,h])=>(
          <div key={k} style={rowStyle}>
            <div style={keyStyle}>{k}</div>
            <span style={valStyle(h)}>{v}</span>
          </div>
        ))}
      </div>

      {/* Connector */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 72, flexShrink: 0 }}>
        <div style={{
          fontSize: 10, fontWeight: 600, color: C.gold,
          background: C.goldLight, border: `1px solid ${C.gold}22`,
          padding: "2px 8px", borderRadius: 20, marginBottom: 6,
          opacity: matched ? 1 : 0,
          transform: matched ? "none" : "scale(0.6)",
          transition: "all 0.4s cubic-bezier(.34,1.56,.64,1) 0.9s",
          whiteSpace: "nowrap",
        }}>0.9832</div>
        <div style={{
          height: 1, width: "100%",
          background: `linear-gradient(90deg, ${C.border}, ${C.gold}, ${C.border})`,
          opacity: matched ? 1 : 0,
          transform: matched ? "scaleX(1)" : "scaleX(0)",
          transformOrigin: "left",
          transition: "opacity 0.3s 0.5s, transform 0.6s cubic-bezier(.2,1,.3,1) 0.5s",
        }} />
      </div>

      {/* Ledger */}
      <div style={{
        ...docStyle,
        borderColor: matched ? `${C.gold}66` : C.border,
        opacity: matched ? 1 : 0,
        transform: matched ? "none" : "translateX(16px)",
        transition: `all 0.6s cubic-bezier(.2,1,.3,1) 0.1s, border-color 0.5s 1.1s`,
      }}>
        <div style={labelStyle}>Ledger entry</div>
        {[["Ref.","INV2024047",true],["Party","Himalayan Traders",true],["Date","16 Jan 2024",false],["Debit","₹45,000",false]].map(([k,v,h])=>(
          <div key={k} style={rowStyle}>
            <div style={keyStyle}>{k}</div>
            <span style={valStyle(h)}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Feature card ───────────────────────────────────────────────────────── */
function FeatureCard({ icon, title, body, delay }) {
  return (
    <Reveal delay={delay}>
      <div style={{
        background: C.bg,
        border: `1px solid ${C.border}`,
        borderRadius: 8,
        padding: "28px 24px",
      }}>
        <div style={{ color: C.text, marginBottom: 16 }}>{icon}</div>
        <div style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: 17, fontWeight: 600,
          color: C.text, marginBottom: 10, lineHeight: 1.3,
        }}>{title}</div>
        <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.7 }}>{body}</div>
      </div>
    </Reveal>
  );
}

/* ─── How-it-works step ──────────────────────────────────────────────────── */
function Step({ n, title, body, last, delay }) {
  return (
    <Reveal delay={delay}>
      <div style={{ display: "flex", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%",
            border: `1.5px solid ${C.text}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "'Playfair Display', serif",
            fontSize: 14, fontWeight: 600, color: C.text,
          }}>{n}</div>
          {!last && <div style={{ width: 1, flex: 1, background: C.border, margin: "8px 0", minHeight: 36 }} />}
        </div>
        <div style={{ paddingBottom: last ? 0 : 32, paddingTop: 6 }}>
          <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 16, fontWeight: 600, color: C.text, marginBottom: 6 }}>{title}</div>
          <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.65 }}>{body}</div>
        </div>
      </div>
    </Reveal>
  );
}

/* ─── Landing page ───────────────────────────────────────────────────────── */
export function LandingPage() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 30);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);

  const go = () => navigate("/app");

  const navLink = { fontSize: 13, color: C.textMuted, textDecoration: "none", letterSpacing: "0.02em" };

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text,
      fontFamily: "'Inter', sans-serif" }}>

      {/* ── NAV ── */}
      <nav style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        background: scrolled ? "rgba(255,255,255,0.96)" : "transparent",
        backdropFilter: scrolled ? "blur(10px)" : "none",
        borderBottom: scrolled ? `1px solid ${C.border}` : "1px solid transparent",
        transition: "all 0.3s",
        height: 58, display: "flex", alignItems: "center",
        padding: "0 48px", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <IcoLink size={18} />
          <span style={{ fontFamily: "'Playfair Display', serif", fontWeight: 600, fontSize: 17, letterSpacing: "-0.01em" }}>
            matchIT
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 36 }}>
          {[["Features","#features"],["How it works","#how"],["About","#about"]].map(([l,h]) => (
            <a key={l} href={h} style={navLink}
              onMouseEnter={e => e.target.style.color = C.text}
              onMouseLeave={e => e.target.style.color = C.textMuted}>{l}</a>
          ))}
          <button onClick={go} style={{
            background: C.text, color: "#FFFFFF",
            border: "none", borderRadius: 6,
            padding: "8px 22px", fontSize: 13, fontWeight: 500,
            cursor: "pointer", letterSpacing: "0.01em",
            transition: "opacity 0.15s",
          }}
            onMouseEnter={e => e.currentTarget.style.opacity = "0.85"}
            onMouseLeave={e => e.currentTarget.style.opacity = "1"}>
            Open app
          </button>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section style={{
        minHeight: "100vh",
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        padding: "90px 48px 60px",
        textAlign: "center",
        borderBottom: `1px solid ${C.border}`,
      }}>
        <div style={{
          display: "inline-block",
          fontSize: 11, fontWeight: 500,
          color: C.textMuted, letterSpacing: "0.12em",
          textTransform: "uppercase",
          borderBottom: `1px solid ${C.borderMid}`,
          paddingBottom: 8, marginBottom: 36,
        }}>
          Document reconciliation system
        </div>

        <h1 style={{
          fontFamily: "'Playfair Display', serif",
          fontSize: "clamp(36px, 5.5vw, 68px)",
          fontWeight: 700, lineHeight: 1.06,
          letterSpacing: "-0.02em",
          margin: "0 0 12px",
          maxWidth: 760,
        }}>
          Invoice matching,
          <br />
          <em style={{ fontStyle: "italic", color: C.textMid }}>done in seconds.</em>
        </h1>

        <p style={{
          fontSize: 17, color: C.textMuted,
          maxWidth: 500, lineHeight: 1.7,
          margin: "20px 0 44px",
        }}>
          Upload your invoices and ledger. matchIT reconciles them automatically,
          handling format differences, date offsets, and vendor name variations.
        </p>

        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 80 }}>
          <button onClick={go} style={{
            background: C.text, color: "#FFFFFF",
            border: "none", borderRadius: 6,
            padding: "14px 34px", fontSize: 15, fontWeight: 500,
            cursor: "pointer", display: "flex", alignItems: "center", gap: 9,
            transition: "opacity 0.15s", letterSpacing: "0.01em",
          }}
            onMouseEnter={e => e.currentTarget.style.opacity = "0.85"}
            onMouseLeave={e => e.currentTarget.style.opacity = "1"}>
            Try matchIT now <IcoArrowRight size={16} />
          </button>
          <a href="#how" style={{
            color: C.textMuted, fontSize: 14, textDecoration: "none",
            display: "flex", alignItems: "center", gap: 6,
            borderBottom: `1px solid ${C.border}`, paddingBottom: 1,
            transition: "color 0.15s",
          }}
            onMouseEnter={e => e.currentTarget.style.color = C.text}
            onMouseLeave={e => e.currentTarget.style.color = C.textMuted}>
            See how it works <IcoArrowDown size={13} />
          </a>
        </div>

        {/* Hero visual */}
        <div style={{ position: "relative" }}>
          <HeroDoc />
          {/* Status chips */}
          <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 24 }}>
            {[
              { l: "Auto match",  bg: "#EEFBE8", text: "#2A6016" },
              { l: "Needs review",bg: C.goldLight, text: C.gold    },
              { l: "Unmatched",   bg: "#FBE8E8", text: "#961010"  },
            ].map(({ l, bg, text }) => (
              <div key={l} style={{
                background: bg, color: text,
                fontSize: 11, fontWeight: 500,
                padding: "4px 12px", borderRadius: 20,
                letterSpacing: "0.04em",
              }}>{l}</div>
            ))}
          </div>
        </div>
      </section>

      {/* ── STATS BAR ── */}
      <section style={{
        background: C.bgAlt,
        borderBottom: `1px solid ${C.border}`,
        padding: "44px 48px",
      }}>
        <div style={{
          maxWidth: 840, margin: "0 auto",
          display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
          gap: 0,
        }}>
          {[
            ["4 fields","compared per invoice pair"],
            ["< 0.1s","matching engine runtime"],
            ["3 tiers","auto / review / unmatched"],
            ["100%","explainable decisions"],
          ].map(([val, lbl], i) => (
            <div key={lbl} style={{
              textAlign: "center", padding: "0 24px",
              borderRight: i < 3 ? `1px solid ${C.border}` : "none",
            }}>
              <div style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: 28, fontWeight: 700,
                color: C.text, letterSpacing: "-0.02em", marginBottom: 4,
              }}>{val}</div>
              <div style={{ fontSize: 12, color: C.textMuted, letterSpacing: "0.03em" }}>{lbl}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section id="features" style={{ padding: "96px 48px" }}>
        <div style={{ maxWidth: 1020, margin: "0 auto" }}>
          <Reveal>
            <div style={{ marginBottom: 56 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: C.textMuted,
                letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 14 }}>
                Capabilities
              </div>
              <h2 style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: 36, fontWeight: 700,
                letterSpacing: "-0.02em", color: C.text, margin: 0,
              }}>
                Everything reconciliation requires.
              </h2>
            </div>
          </Reveal>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
            {[
              { icon: <IcoFile />,     title: "Multi-format extraction",   delay: 0,   body: "Excel, CSV, PDF, and scanned images all accepted. File type is detected automatically — OCR loads only when an image or PDF is uploaded." },
              { icon: <IcoTarget />,   title: "Fuzzy field matching",      delay: 80,  body: "Levenshtein for reference numbers, Jaro-Winkler for vendor names, tolerance windows for dates, relative-error decay for amounts." },
              { icon: <IcoGrid />,     title: "Global optimisation",       delay: 160, body: "The Hungarian algorithm assigns every invoice to a ledger entry simultaneously, maximising total match quality — not a greedy pair-by-pair lookup." },
              { icon: <IcoEye />,      title: "Explainable scores",        delay: 0,   body: "Every match shows which fields matched, how closely, and how much each contributed to the final score. Nothing is hidden." },
              { icon: <IcoLink size={22}/>, title: "Session persistence", delay: 80,  body: "Past reconciliation sessions are cached in PostgreSQL. Re-open any previous session and results are returned instantly." },
              { icon: <IcoDownload />, title: "Export and override",       delay: 160, body: "Download results as CSV or JSON. Override any automated decision with a note — all corrections are logged." },
            ].map(p => <FeatureCard key={p.title} {...p} />)}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section id="how" style={{
        background: C.bgAlt,
        borderTop: `1px solid ${C.border}`,
        borderBottom: `1px solid ${C.border}`,
        padding: "96px 48px",
      }}>
        <div style={{
          maxWidth: 1020, margin: "0 auto",
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 80, alignItems: "start",
        }}>
          <div>
            <Reveal>
              <div style={{ fontSize: 11, fontWeight: 500, color: C.textMuted,
                letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 14 }}>
                How it works
              </div>
              <h2 style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: 34, fontWeight: 700,
                letterSpacing: "-0.02em", color: C.text, margin: "0 0 18px",
              }}>
                Five stages.<br /><em style={{ fontStyle: "italic" }}>One result.</em>
              </h2>
              <p style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.7, margin: "0 0 36px" }}>
                The pipeline is fully transparent — every stage is inspectable,
                every decision explainable.
              </p>
            </Reveal>

            {/* Format pills */}
            <Reveal delay={100}>
              <div style={{
                border: `1px solid ${C.border}`, borderRadius: 8,
                padding: "18px 20px", background: C.bg,
              }}>
                <div style={{ fontSize: 11, color: C.textMuted,
                  letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 12 }}>
                  Supported formats
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {[".xlsx",".csv",".pdf",".jpg",".png"].map(f => (
                    <span key={f} style={{
                      background: C.bgAlt, border: `1px solid ${C.border}`,
                      color: C.text, fontSize: 12, padding: "3px 10px",
                      borderRadius: 4, fontFamily: "monospace",
                    }}>{f}</span>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>

          <div style={{ paddingTop: 4 }}>
            {[
              { n:1, title:"Upload documents",      body:"Drop invoice files and ledger files. Excel and CSV are parsed directly; PDFs and images go through OCR." },
              { n:2, title:"Field extraction",      body:"Invoice number, vendor name, date, and amount are identified from each file by rule-based detection." },
              { n:3, title:"Normalisation",         body:"Reference numbers, vendor names, dates, and amounts are cleaned and standardised before comparison." },
              { n:4, title:"Scoring and matching",  body:"A weighted similarity score is computed for every pair. The Hungarian algorithm finds the optimal global assignment." },
              { n:5, title:"Review results",        body:"Each pair is classified as Auto Match, Review, or Unmatched. Expand any card to see the field-level breakdown.", last:true },
            ].map((s,i) => <Step key={s.n} delay={i*80} {...s} />)}
          </div>
        </div>
      </section>

      {/* ── WHY MATCHIT ── */}
      <section id="about" style={{ padding: "96px 48px" }}>
        <div style={{
          maxWidth: 1020, margin: "0 auto",
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 80, alignItems: "center",
        }}>
          {/* Result mock */}
          <Reveal>
            <div style={{
              border: `1px solid ${C.border}`, borderRadius: 8,
              padding: "32px 28px", background: C.bgAlt,
            }}>
              <div style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: 16, fontWeight: 600, color: C.text, marginBottom: 24,
              }}>
                Reconciliation complete
              </div>

              {[
                { label:"7 pairs auto-matched",   sub:"Score ≥ 0.90 — no review needed",  dot:"#2A6016", bg:"#EEFBE8" },
                { label:"2 flagged for review",   sub:"Score 0.70–0.89 — verify manually", dot:C.gold,    bg:C.goldLight },
                { label:"1 invoice unmatched",    sub:"No ledger counterpart found",        dot:"#961010", bg:"#FBE8E8" },
              ].map(({ label, sub, dot, bg }) => (
                <div key={label} style={{
                  display: "flex", gap: 14, alignItems: "flex-start",
                  padding: "14px 0", borderBottom: `1px solid ${C.border}`,
                }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%",
                    background: dot, marginTop: 5, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: C.text }}>{label}</div>
                    <div style={{ fontSize: 12, color: C.textMuted, marginTop: 2 }}>{sub}</div>
                  </div>
                </div>
              ))}

              <div style={{
                marginTop: 20, padding: "14px 16px",
                background: C.goldLight, borderRadius: 6,
                border: `1px solid ${C.gold}33`,
              }}>
                <div style={{ fontSize: 11, color: C.gold, fontWeight: 500,
                  letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 4 }}>
                  Time saved
                </div>
                <div style={{
                  fontFamily: "'Playfair Display', serif",
                  fontSize: 22, fontWeight: 700, color: C.text, letterSpacing: "-0.02em",
                }}>
                  ~3.5 hours → 8 seconds
                </div>
              </div>
            </div>
          </Reveal>

          {/* Text */}
          <div>
            <Reveal>
              <div style={{ fontSize: 11, fontWeight: 500, color: C.textMuted,
                letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 14 }}>
                Why matchIT
              </div>
              <h2 style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: 34, fontWeight: 700,
                letterSpacing: "-0.02em", color: C.text, margin: "0 0 18px",
              }}>
                Built for messy<br /><em style={{ fontStyle: "italic" }}>real-world data.</em>
              </h2>
              <p style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.75, marginBottom: 28 }}>
                Real invoices and ledger entries rarely match exactly. Reference
                numbers get reformatted, vendor names get abbreviated, payment
                dates drift, amounts differ by rounding. Standard lookup fails on all of these.
              </p>
            </Reveal>
            <Reveal delay={80}>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[
                  "Handles INV-2024-001 matching INV2024001 automatically",
                  "Tolerates vendor abbreviations and legal suffix variants",
                  "Date offsets up to 3 days scored as near-perfect matches",
                  "Amount differences within 1% treated as exact",
                  "Globally optimal one-to-one assignment via Hungarian algorithm",
                  "Every decision is fully explainable and overridable",
                ].map(p => (
                  <div key={p} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                    <div style={{ marginTop: 1, flexShrink: 0 }}><IcoCheck /></div>
                    <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.5 }}>{p}</div>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section style={{
        background: C.bgAlt,
        borderTop: `1px solid ${C.border}`,
        padding: "96px 48px",
        textAlign: "center",
      }}>
        <Reveal>
          <div style={{ maxWidth: 520, margin: "0 auto" }}>
            <h2 style={{
              fontFamily: "'Playfair Display', serif",
              fontSize: 40, fontWeight: 700,
              letterSpacing: "-0.03em", color: C.text,
              margin: "0 0 18px", lineHeight: 1.1,
            }}>
              Ready to stop matching<br /><em style={{ fontStyle: "italic" }}>invoices by hand?</em>
            </h2>
            <p style={{ color: C.textMuted, fontSize: 15, lineHeight: 1.7, marginBottom: 36 }}>
              Upload your first batch and see results in seconds.
            </p>
            <button onClick={go} style={{
              background: C.text, color: "#FFFFFF",
              border: "none", borderRadius: 6,
              padding: "16px 44px", fontSize: 15, fontWeight: 500,
              cursor: "pointer",
              display: "inline-flex", alignItems: "center", gap: 10,
              transition: "opacity 0.15s", letterSpacing: "0.01em",
            }}
              onMouseEnter={e => e.currentTarget.style.opacity = "0.85"}
              onMouseLeave={e => e.currentTarget.style.opacity = "1"}>
              Try matchIT now <IcoArrowRight size={16} />
            </button>
            <div style={{ marginTop: 16, fontSize: 12, color: C.textMuted }}>
              No sign-up required · Excel, CSV, PDF, and images accepted
            </div>
          </div>
        </Reveal>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{
        borderTop: `1px solid ${C.border}`,
        padding: "24px 48px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <IcoLink size={15} />
          <span style={{ fontFamily: "'Playfair Display', serif", fontWeight: 600, fontSize: 15 }}>matchIT</span>
          <span style={{ color: C.textMuted, fontSize: 13 }}>— Document Reconciliation System</span>
        </div>
        <div style={{ color: C.textMuted, fontSize: 12 }}>
          Trinity International College · TU BSc.CSIT · 2083
        </div>
      </footer>
    </div>
  );
}