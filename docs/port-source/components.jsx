/* eslint-disable no-undef */
// Shared components, helpers, and icons used across routes.

const { useState, useEffect, useRef, useMemo, useCallback, useLayoutEffect } = React;

// ── Slide accent palette ───────────────────────────────────
// 10-color hardcoded palette indexed by slide ordinal (i % 10).
// Promoted out of inline arrays into a single shared map so every consumer
// (slide rail, segments, minimap, STT/Discrepancies, Session Detail) reads
// the same source. Precomputed Map = O(1) lookup; no per-render scans.
const SLIDE_PALETTE = [
  "#2563eb", "#7c3aed", "#059669", "#d97706", "#dc2626",
  "#0891b2", "#6366f1", "#ea580c", "#0d9488", "#be185d",
];
const _slideAccentMap = new Map(MIC_DATA.SLIDES.map((s, i) => [s.id, SLIDE_PALETTE[i % SLIDE_PALETTE.length]]));
const _slideByIdMap   = new Map(MIC_DATA.SLIDES.map((s) => [s.id, s]));
function slideAccent(slideId) { return _slideAccentMap.get(slideId) || "#4D6995"; }
function slideById(slideId)   { return _slideByIdMap.get(slideId); }

// Compose a hex#RRGGBB + 2-digit alpha suffix, with safety fall-through.
function withAlpha(hex, alphaHex) {
  if (!hex || hex[0] !== "#" || hex.length !== 7) return hex;
  return hex + alphaHex;
}

// ── Time helpers ───────────────────────────────────────────
function fmtTime(sec) {
  if (sec == null || isNaN(sec)) return "--:--";
  const s = Math.floor(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s - h * 3600) / 60);
  const ss = s - h * 3600 - m * 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  return `${m}:${String(ss).padStart(2, "0")}`;
}
function fmtClock(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: false });
}

// ── Inline SVG icon set (subset matching VIN's icon weight) ─
function Icon({ name, size = 14, className = "" }) {
  const props = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", className, "aria-hidden": true };
  switch (name) {
    case "play":   return <svg {...props}><polygon points="6 4 20 12 6 20 6 4" fill="currentColor" stroke="none"/></svg>;
    case "pause":  return <svg {...props}><rect x="6" y="4" width="4" height="16" fill="currentColor" stroke="none"/><rect x="14" y="4" width="4" height="16" fill="currentColor" stroke="none"/></svg>;
    case "skip-back":    return <svg {...props}><polygon points="19 20 9 12 19 4 19 20" fill="currentColor" stroke="none"/><line x1="5" y1="19" x2="5" y2="5"/></svg>;
    case "skip-forward": return <svg {...props}><polygon points="5 4 15 12 5 20 5 4" fill="currentColor" stroke="none"/><line x1="19" y1="5" x2="19" y2="19"/></svg>;
    case "search": return <svg {...props}><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
    case "filter": return <svg {...props}><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" fill="currentColor" stroke="none" fillOpacity="0.85"/></svg>;
    case "more":   return <svg {...props}><circle cx="5" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.5" fill="currentColor" stroke="none"/></svg>;
    case "edit":   return <svg {...props}><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" fill="currentColor" fillOpacity="0.18"/></svg>;
    case "check":  return <svg {...props}><polyline points="20 6 9 17 4 12"/></svg>;
    case "x":      return <svg {...props}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>;
    case "flag":   return <svg {...props}><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" fill="currentColor" fillOpacity="0.2"/><line x1="4" y1="22" x2="4" y2="15"/></svg>;
    case "alert":  return <svg {...props}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" fill="currentColor" fillOpacity="0.15"/><line x1="12" y1="9"  x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>;
    case "chevron-down":  return <svg {...props}><polyline points="6 9 12 15 18 9"/></svg>;
    case "chevron-right": return <svg {...props}><polyline points="9 18 15 12 9 6"/></svg>;
    case "chevron-left":  return <svg {...props}><polyline points="15 18 9 12 15 6"/></svg>;
    case "users":  return <svg {...props}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>;
    case "message":return <svg {...props}><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>;
    case "list":   return <svg {...props}><line x1="8"  y1="6"  x2="21" y2="6"/><line x1="8"  y1="12" x2="21" y2="12"/><line x1="8"  y1="18" x2="21" y2="18"/><line x1="3"  y1="6"  x2="3.01" y2="6"/><line x1="3"  y1="12" x2="3.01" y2="12"/><line x1="3"  y1="18" x2="3.01" y2="18"/></svg>;
    case "user":   return <svg {...props}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
    case "settings": return <svg {...props}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
    case "history":return <svg {...props}><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/><polyline points="12 7 12 12 16 14"/></svg>;
    case "activity": return <svg {...props}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
    case "download": return <svg {...props}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>;
    case "external":return <svg {...props}><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>;
    case "save":   return <svg {...props}><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>;
    case "git":    return <svg {...props}><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/></svg>;
    case "grip":   return <svg {...props}><circle cx="9" cy="6" r="1" fill="currentColor"/><circle cx="9" cy="12" r="1" fill="currentColor"/><circle cx="9" cy="18" r="1" fill="currentColor"/><circle cx="15" cy="6" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="18" r="1" fill="currentColor"/></svg>;
    case "split":  return <svg {...props}><line x1="3" y1="12" x2="21" y2="12"/><polyline points="3 12 8 7 8 17 3 12"/></svg>;
    case "merge":  return <svg {...props}><circle cx="6" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M9 6h7a3 3 0 0 1 3 3v6"/><path d="M6 9v9"/></svg>;
    case "speaker":return <svg {...props}><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor" fillOpacity="0.2"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>;
    case "slide":  return <svg {...props}><rect x="3" y="5" width="18" height="14" rx="2"/><line x1="7" y1="9" x2="17" y2="9"/><line x1="7" y1="13" x2="13" y2="13"/></svg>;
    case "anchor": return <svg {...props}><circle cx="12" cy="5" r="3"/><line x1="12" y1="22" x2="12" y2="8"/><path d="M5 12H2a10 10 0 0 0 20 0h-3"/></svg>;
    case "pin":    return <svg {...props}><line x1="12" y1="17" x2="12" y2="22"/><path d="M9 10V3h6v7l3 4H6l3-4z" fill="currentColor" fillOpacity="0.15"/></svg>;
    case "lightning": return <svg {...props}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" fill="currentColor" fillOpacity="0.18"/></svg>;
    case "shield": return <svg {...props}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="currentColor" fillOpacity="0.15"/></svg>;
    case "doc":    return <svg {...props}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>;
    case "branch": return <svg {...props}><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>;
    case "globe":  return <svg {...props}><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>;
    case "circle-dot": return <svg {...props}><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/></svg>;
    case "spinner": return (
      <svg {...props}><circle cx="12" cy="12" r="10" opacity="0.2"/><path d="M12 2a10 10 0 0 1 10 10"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/></path></svg>
    );
    default: return <svg {...props}><circle cx="12" cy="12" r="4"/></svg>;
  }
}

// ── Stage badge ────────────────────────────────────────────
function StageBadge({ id }) {
  const stages = MIC_DATA.SOP_STAGES;
  const s = stages.find((x) => x.id === id);
  if (!s) return null;
  return <span className={`stage-badge stage-badge--${id}`}>{s.order}. {s.name}</span>;
}

// ── Avatar / stack ─────────────────────────────────────────
function Avatar({ name, color, size = 24, ring = true }) {
  const initials = (name || "?").split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  return (
    <span className="avatar" style={{
      width: size, height: size, borderRadius: "50%",
      background: color || "var(--color-steel)", color: "#fff",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      fontSize: Math.round(size * 0.4), fontWeight: 800,
      border: ring ? "2px solid var(--surface-card)" : "none",
      flexShrink: 0,
    }}>{initials}</span>
  );
}

function AvatarStack({ initials = [], max = 4 }) {
  const palette = ["#002855", "#007D61", "#0861CE", "#B9975B", "#4D6995"];
  const shown = initials.slice(0, max);
  const rest = initials.length - shown.length;
  return (
    <div className="avatar-stack">
      {shown.map((i, idx) => (
        <span key={i + idx} className="avatar-stack__a" style={{ background: palette[idx % palette.length] }}>{i}</span>
      ))}
      {rest > 0 ? <span className="avatar-stack__more">+{rest}</span> : null}
    </div>
  );
}

// ── Hash router primitives ─────────────────────────────────
function useHashRoute() {
  const get = () => (window.location.hash || "#/sessions").slice(1);
  const [path, setPath] = useState(get);
  useEffect(() => {
    const onChange = () => setPath(get());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return path;
}
function navigate(path) {
  window.location.hash = path;
}
function Link({ to, children, className = "", onClick, ...rest }) {
  return (
    <a href={`#${to}`} className={className} onClick={(e) => { if (onClick) onClick(e); }} {...rest}>
      {children}
    </a>
  );
}

// Match a hash path against a pattern. Returns null or { params }.
function matchRoute(path, pattern) {
  const ph = path.split("?")[0].replace(/\/$/, "");
  const pp = pattern.replace(/\/$/, "");
  const ps = ph.split("/").filter(Boolean);
  const qs = pp.split("/").filter(Boolean);
  if (ps.length !== qs.length) return null;
  const params = {};
  for (let i = 0; i < qs.length; i++) {
    if (qs[i].startsWith(":")) params[qs[i].slice(1)] = decodeURIComponent(ps[i]);
    else if (qs[i] !== ps[i]) return null;
  }
  return { params };
}

// ── App header ─────────────────────────────────────────────
function AppHeader({ build = "v4.0.0-ssot-r2" }) {
  const path = useHashRoute();
  const isActive = (prefixes) => prefixes.some((p) => path.startsWith(p));
  return (
    <header className="app-header" data-screen-label="App Header">
      <Link to="/sessions" className="app-header__brand" aria-label="transcript.software home">
        <img src="assets/VIN-light.svg" alt="VIN" />
        <span className="app-header__divider" />
        <span className="app-header__product">transcript<strong>.software</strong></span>
      </Link>
      <span className="app-header__build" title={`Build ${build}`}>{build}</span>
      <nav className="app-header__nav" aria-label="Primary">
        <Link to="/dashboard"     className={isActive(["/dashboard"]) ? "is-active" : ""}>Dashboard</Link>
        <Link to="/sessions"      className={isActive(["/sessions", "/s/", "/v/", "/e/", "/p/"]) ? "is-active" : ""}>Sessions</Link>
        <Link to="/upload"        className={isActive(["/upload"]) ? "is-active" : ""}>Upload</Link>
        <Link to="/improvements"  className={isActive(["/improvements"]) ? "is-active" : ""}>Improvements</Link>
        <Link to="/settings"      className={isActive(["/settings", "/audit", "/gcs"]) ? "is-active" : ""}>Settings</Link>
      </nav>
      <div className="app-header__tools" aria-label="Quick tools">
        <button className="app-header__icon-btn" title="Search routes (⌘K)" aria-label="Search" data-test-id="topbar-search" onClick={() => wired.openCmdK()}>
          <Icon name="search" size={14} />
        </button>
        <span className="app-header__divider" />
        <button className="app-header__icon-btn app-header__icon-btn--mono" title="Decrease font size" aria-label="Decrease font size" data-test-id="topbar-font-decrease" onClick={() => wired.fontSize(-1)}>A−</button>
        <button className="app-header__icon-btn app-header__icon-btn--mono" title="Increase font size" aria-label="Increase font size" data-test-id="topbar-font-increase" onClick={() => wired.fontSize(+1)}>A+</button>
        <span className="app-header__divider" />
        <span className="app-header__status" title="System status: nominal">
          <span className="dot" /> nominal
        </span>
      </div>
      <div className="app-header__user" title="Logged in as Kate Schultz">
        <span className="app-header__avatar">KS</span>
        <span style={{ marginRight: 4 }}>Kate Schultz</span>
        <button className="app-header__icon-btn app-header__icon-btn--mono" title="Logout" data-test-id="topbar-logout" style={{ marginLeft: 8 }} onClick={wired.logout}>Logout</button>
      </div>
    </header>
  );
}

// ── Side nav (sessions list, library, etc.) ────────────────
function SideNav({ active = "all" }) {
  const counts = useMemo(() => ({
    all:        MIC_DATA.SESSIONS.length,
    active:     MIC_DATA.SESSIONS.filter((s) => s.status === "active").length,
    processing: MIC_DATA.SESSIONS.filter((s) => s.status === "processing").length,
    complete:   MIC_DATA.SESSIONS.filter((s) => s.status === "complete").length,
    needs:      MIC_DATA.SESSIONS.reduce((a, s) => a + (s.needsReviewCount || 0), 0),
  }), []);
  const items = [
    { id: "all",        label: "All Sessions",      icon: "list",       to: "/sessions",        count: counts.all },
    { id: "active",     label: "In Workflow",       icon: "activity",   to: "/sessions?f=active",     count: counts.active },
    { id: "needs",      label: "Needs Review",      icon: "alert",      to: "/sessions?f=needs",      count: counts.needs },
    { id: "processing", label: "Processing Queue",  icon: "spinner",    to: "/sessions?f=processing", count: counts.processing },
    { id: "complete",   label: "Published",         icon: "check",      to: "/sessions?f=complete",   count: counts.complete },
  ];
  const tools = [
    { id: "audit",     label: "Audit Ledger",   icon: "history",  to: "/audit" },
    { id: "improv",    label: "Improvements",   icon: "lightning", to: "/improvements" },
    { id: "gcs",       label: "GCS Pipeline",   icon: "shield",   to: "/gcs" },
    { id: "settings",  label: "Settings",       icon: "settings", to: "/settings" },
  ];
  return (
    <nav className="app-sidenav" aria-label="Workspace">
      <div>
        <h2 className="app-sidenav__heading">Workspace</h2>
        <ul className="app-sidenav__list">
          {items.map((it) => (
            <li key={it.id} className="app-sidenav__item">
              <Link to={it.to} className={active === it.id ? "is-active" : ""}>
                <Icon name={it.icon} size={14} />
                <span>{it.label}</span>
                {it.count != null ? <span className="app-sidenav__count">{it.count}</span> : null}
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h2 className="app-sidenav__heading">Tools</h2>
        <ul className="app-sidenav__list">
          {tools.map((it) => (
            <li key={it.id} className="app-sidenav__item">
              <Link to={it.to} className={active === it.id ? "is-active" : ""}>
                <Icon name={it.icon} size={14} />
                <span>{it.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <div className="app-sidenav__footer">
        Vue 3 · Pinia · Vite — v4.0.0-ssot-r2
        <code>session uptime: 4h 12m · ws: connected · 18ms RTT</code>
      </div>
    </nav>
  );
}

// ── Word-renderer with AI-flag overlays + active-word highlight
function SegmentText({ text, flags = [], activeWordIdx = -1, onWordClick }) {
  const words = useMemo(() => text.split(/(\s+)/), [text]);
  const flagByWord = useMemo(() => {
    const m = new Map();
    flags.forEach((f) => m.set(f.w, f.kind));
    return m;
  }, [flags]);

  let wordIdx = -1;
  return (
    <span className="segment__text">
      {words.map((tok, i) => {
        if (/^\s+$/.test(tok)) return <span key={i}>{tok}</span>;
        wordIdx++;
        const kind = flagByWord.get(wordIdx);
        const isCur = wordIdx === activeWordIdx;
        const cls = ["word"];
        if (kind) cls.push(`flag-${kind}`);
        if (isCur) cls.push("is-current");
        const w = wordIdx;
        return (
          <span key={i} className={cls.join(" ")} onClick={(e) => { e.stopPropagation(); onWordClick && onWordClick(w); }}>{tok}</span>
        );
      })}
    </span>
  );
}

// ── Tooltip-y press chip ───────────────────────────────────
function FlagLegend() {
  return (
    <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--fg2)", alignItems: "center" }}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <em className="word flag-drift"  style={{ display: "inline-block", padding: "0 6px", borderRadius: 2 }}>drift</em>
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <em className="word flag-uncertain" style={{ display: "inline-block", padding: "0 6px", borderRadius: 2 }}>uncertain</em>
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <em className="word flag-low_confidence" style={{ display: "inline-block", padding: "0 6px", borderRadius: 2 }}>low confidence</em>
      </span>
    </div>
  );
}

// Export everything to window
Object.assign(window, {
  useState, useEffect, useRef, useMemo, useCallback, useLayoutEffect,
  fmtTime, fmtClock, Icon, StageBadge, Avatar, AvatarStack,
  useHashRoute, navigate, Link, matchRoute,
  AppHeader, SideNav, SegmentText, FlagLegend,
  SLIDE_PALETTE, slideAccent, slideById, withAlpha,
});
