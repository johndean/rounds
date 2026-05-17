/* eslint-disable no-undef */
// Discrepancies tab (inside editor), Audit tab (inside editor),
// and standalone Audit / Word Track Changes route.

// ── Discrepancies (renders inside the editor route) ────────
// Side-by-side AI Transcript ↔ STT Raw, with inline difference highlighting.
function DiscrepanciesPane({ activeSegmentId, onSegmentClick, focusedSlideId, slideRailMode, onClearFocus }) {
  // Three modes: all (every segment, full transcript), flagged (any discrepancy), meaningful (meaningful only)
  const [mode, setMode] = useState("flagged");

  const segments = MIC_DATA.SEGMENTS;
  const flagsBySeg = useMemo(() => {
    const m = new Map();
    MIC_DATA.DISCREPANCIES.forEach((d) => {
      if (!m.has(d.seg)) m.set(d.seg, []);
      m.get(d.seg).push(d);
    });
    return m;
  }, []);

  const flaggedSegmentIds = useMemo(() => new Set(MIC_DATA.DISCREPANCIES.map((d) => d.seg)), []);
  const meaningfulSegmentIds = useMemo(
    () => new Set(MIC_DATA.DISCREPANCIES.filter((d) => d.meaningful).map((d) => d.seg)),
    []
  );

  const visibleSegments = useMemo(() => {
    let pool = segments;
    if (slideRailMode === "filter" && focusedSlideId) {
      pool = pool.filter((s) => s.slide_id === focusedSlideId);
    }
    if (mode === "all")        return pool;
    if (mode === "flagged")    return pool.filter((s) => flaggedSegmentIds.has(s.id));
    if (mode === "meaningful") return pool.filter((s) => meaningfulSegmentIds.has(s.id));
    return pool;
  }, [segments, mode, flaggedSegmentIds, meaningfulSegmentIds, focusedSlideId, slideRailMode]);

  const totalDiffs = MIC_DATA.DISCREPANCIES.length;
  const meaningfulCount = MIC_DATA.DISCREPANCIES.filter((d) => d.meaningful).length;

  // STT-shaped text: lowercase, no punctuation, drift swaps applied
  const renderSTT = (seg) => {
    const diffs = flagsBySeg.get(seg.id) || [];
    let stt = seg.text.toLowerCase().replace(/[.,;!?—–]/g, "");
    diffs.forEach((d) => {
      if (d.kind === "drift") {
        const baseFrag = d.base.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        try {
          stt = stt.replace(new RegExp(baseFrag, "i"), d.stt.toLowerCase());
        } catch (e) { /* noop */ }
      }
    });
    if (!diffs.length) return stt;
    let html = stt;
    diffs.forEach((d) => {
      if (d.kind === "drift") {
        const sttFrag = d.stt.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        try {
          html = html.replace(new RegExp(`(${sttFrag})`, "i"), `<mark class="compare-diff">$1</mark>`);
        } catch (e) { /* noop */ }
      }
    });
    return <span dangerouslySetInnerHTML={{ __html: html }} />;
  };

  return (
    <section className="compare" data-screen-label="Discrepancies — AI ↔ STT compare">
      {slideRailMode === "filter" && focusedSlideId ? (
        <div className="transcript__filter-banner" role="status" style={{ margin: "10px 18px 0" }}>
          <Icon name="filter" size={14} />
          <span><strong>Filter mode:</strong> showing {visibleSegments.length} segments on slide {focusedSlideId.replace("s", "")}.</span>
          <button className="btn btn--tertiary btn--sm" onClick={onClearFocus}>Clear filter</button>
        </div>
      ) : null}
      <div className="compare__toolbar compare__toolbar--top">
        <div className="count">
          <strong style={{ color: "var(--color-amber)" }}>{meaningfulCount}</strong> flagged for review · {totalDiffs} raw diffs
        </div>
        <div className="compare__modes" role="radiogroup" aria-label="Filter mode">
          <button className={mode === "all" ? "is-active" : ""}        onClick={() => setMode("all")}        role="radio" aria-checked={mode === "all"}>
            All <span className="count-pill">{segments.length}</span>
          </button>
          <button className={mode === "flagged" ? "is-active" : ""}    onClick={() => setMode("flagged")}    role="radio" aria-checked={mode === "flagged"}>
            Flagged <span className="count-pill">{flaggedSegmentIds.size}</span>
          </button>
          <button className={mode === "meaningful" ? "is-active" : ""} onClick={() => setMode("meaningful")} role="radio" aria-checked={mode === "meaningful"}>
            Meaningful <span className="count-pill">{meaningfulSegmentIds.size}</span>
          </button>
        </div>
      </div>

      <div className="compare__split">
        <div className="compare__col-head compare__col-head--ai">
          <Icon name="doc" size={13} /> AI Transcript
        </div>
        <div className="compare__col-head compare__col-head--stt">
          <Icon name="speaker" size={13} /> STT Raw <span className="badge">read-only</span>
        </div>
        {visibleSegments.map((seg) => {
          const sp = MIC_DATA.SPEAKERS[seg.speaker];
          const isFlagged = flaggedSegmentIds.has(seg.id);
          const isActive  = seg.id === activeSegmentId;
          const sl = slideById(seg.slide_id);
          const accent = slideAccent(seg.slide_id);
          return (
            <React.Fragment key={seg.id}>
              <article
                className={`segment compare__row-ai ${isActive ? "is-active" : ""} ${isFlagged ? "is-needs-review" : ""}`}
                style={{ boxShadow: `inset 3px 0 0 ${accent}` }}
                onClick={() => onSegmentClick && onSegmentClick(seg.id)}>
                <header className="segment__header">
                  <span className="segment__slide-chip">
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: accent }} />
                    <strong>{sl ? String(sl.n).padStart(2, "0") : "—"}</strong>
                    <span style={{ opacity: 0.5 }}>·</span>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sl?.title || "Unassigned"}</span>
                  </span>
                  <span className="segment__inline-actions">
                    {isFlagged ? <span className="chip chip--amber" style={{ fontSize: 9, padding: "2px 7px" }}>{(flagsBySeg.get(seg.id) || []).length} diff</span> : null}
                    <button className="segment__inline-action" data-test-id="seg-edit-disc" onClick={(e) => { e.stopPropagation(); wired.openSegmentEdit(seg, () => wired.toastInfo("Segment saved", "ok")); }}>Edit</button>
                    <button className="segment__inline-action" data-test-id="seg-reassign-disc" onClick={(e) => { e.stopPropagation(); wired.reassignSegment(seg); }}>Reassign</button>
                  </span>
                </header>
                <div className="segment__body">
                  <div className="segment__gutter">
                    <span className="segment__time">{fmtTime(seg.start)}</span>
                    <span className={`segment__speaker-pill speaker-${seg.speaker}`}>{sp.short}</span>
                  </div>
                  <div className="segment__main">
                    <SegmentText text={seg.text} flags={seg.ai_flags} activeWordIdx={-1} onWordClick={() => {}} />
                  </div>
                </div>
              </article>
              <article
                className={`stt-segment compare__row-stt ${isActive ? "is-active" : ""}`}
                data-stt-seg={seg.id}
                style={{ boxShadow: `inset 3px 0 0 ${accent}` }}
                onClick={() => onSegmentClick && onSegmentClick(seg.id)}>
                <header className="segment__header" style={{ visibility: "hidden" }} aria-hidden>
                  <span className="segment__slide-chip">
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "transparent" }} />
                    <strong>·</strong>
                  </span>
                </header>
                <div className="stt-segment__gutter">
                  <span className="stt-segment__time">{fmtTime(seg.start)}</span>
                  <span className={`stt-segment__conf ${seg.confidence === "low" ? "low" : ""}`} style={{ color: accent, borderColor: withAlpha(accent, "44") }}>{sl ? `s${String(sl.n).padStart(2, "0")}` : ""}</span>
                </div>
                <div className="stt-segment__main">{renderSTT(seg)}</div>
              </article>
            </React.Fragment>
          );
        })}
        {visibleSegments.length === 0 ? (
          <div className="compare__empty">All clean — no discrepancies matching this filter.</div>
        ) : null}
      </div>
    </section>
  );
}

// ── Audit tab inline (rendered inside editor 3-column frame) ──
// Default sub-view: "Decisions" — production-style WAS / NOW cards.
// Toggle to: "Ledger" — the compact append-only correction-lineage table.
function AuditTabInline({ session, activeSegmentId, onSegmentClick }) {
  const [view, setView] = useState("decisions");
  const segmentsById = useMemo(() => {
    const m = new Map();
    MIC_DATA.SEGMENTS.forEach((s) => m.set(s.id, s));
    return m;
  }, []);

  // Only "decision-making" corrections render as cards; mark_reviewed and
  // annotation_remove are bookkeeping and live only in the ledger.
  const decisionTypes = new Set(["text_edit", "chat_insert", "slide_reassignment", "speaker_reassignment", "annotation_add"]);
  const decisions = useMemo(
    () => MIC_DATA.CORRECTIONS.filter((c) => decisionTypes.has(c.type)).slice().reverse(),
    []
  );

  return (
    <section className="audit-tab" data-screen-label="Audit · Decisions">
      <div className="audit-tab__toolbar">
        <div className="audit-tab__count">
          <strong>{view === "decisions" ? decisions.length : MIC_DATA.CORRECTIONS.length}</strong>
          {view === "decisions" ? " active decisions" : " ledger rows"}
        </div>
        <div className="audit-tab__flags">
          <span className="audit-tab__flag"><span className="dot" style={{ background: "var(--color-red)" }} /> Drift (0)</span>
          <span className="audit-tab__flag"><span className="dot" style={{ background: "var(--color-amber)" }} /> Uncertain (0)</span>
          <span className="audit-tab__flag"><span className="dot" style={{ background: "var(--color-blue)" }} /> Low conf (0)</span>
        </div>
        <div className="audit-tab__viewtoggle" role="radiogroup" aria-label="Audit view">
          <button className={view === "decisions" ? "is-active" : ""} onClick={() => setView("decisions")} role="radio" aria-checked={view === "decisions"}>
            Decisions
          </button>
          <button className={view === "ledger" ? "is-active" : ""} onClick={() => setView("ledger")} role="radio" aria-checked={view === "ledger"}>
            Ledger
          </button>
        </div>
        <div className="audit-tab__actions">
          <Link to={`/e/${session.id}/audit`} className="btn btn--ghost btn--sm"><Icon name="external" /> Full WTC</Link>
          <button className="btn btn--ghost btn--sm" data-test-id="audit-export" onClick={() => { downloadBlob(auditLog.all().map((e) => `${e.t},${e.actor},${e.kind},"${e.summary}"`).join("\n") + "\n", "audit.csv", "text/csv"); toast.push("Audit log exported", { tone: "ok" }); }}><Icon name="download" /> Export</button>
        </div>
      </div>

      {view === "decisions" ? (
        <div className="audit-tab__body">
          {decisions.map((c) => <DecisionCard key={c.id} c={c} segmentsById={segmentsById} onSegmentClick={onSegmentClick} activeSegmentId={activeSegmentId} />)}
          {decisions.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--fg2)" }}>No active decisions.</div>
          ) : null}
        </div>
      ) : (
        <div className="audit-tab__body audit-tab__body--ledger">
          <AuditLedger />
        </div>
      )}
    </section>
  );
}

function DecisionCard({ c, segmentsById, onSegmentClick, activeSegmentId }) {
  const seg = segmentsById.get(c.seg);
  const slide = seg ? MIC_DATA.SLIDES.find((s) => s.id === seg.slide_id) : null;
  const isActive = seg && seg.id === activeSegmentId;

  // Pill label per correction type
  const pill = {
    text_edit:            { label: "edited",          tone: "amber" },
    chat_insert:          { label: "inserted chat",   tone: "amber" },
    slide_reassignment:   { label: "slide reassigned", tone: "amber" },
    speaker_reassignment: { label: "speaker change",  tone: "amber" },
    annotation_add:       { label: "annotation",      tone: "blue" },
  }[c.type] || { label: c.type, tone: "amber" };

  // Build WAS / NOW renders
  let wasContent, nowContent;
  if (c.type === "text_edit" && seg) {
    // Show the fragment swap in context: WAS has prior struck-through;
    // NOW shows next highlighted in green.
    const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    let was = seg.text, now = seg.text;
    try { was = was.replace(new RegExp(`(${esc(c.next)})`, "i"), `<s class="dc-was-strike">${c.prior}</s>`); } catch (e) {}
    try { now = now.replace(new RegExp(`(${esc(c.next)})`, "i"), `<mark class="dc-now-mark">${c.next}</mark>`); } catch (e) {}
    wasContent = <p dangerouslySetInnerHTML={{ __html: was }} />;
    nowContent = <p dangerouslySetInnerHTML={{ __html: now }} />;
  } else if (c.type === "chat_insert") {
    wasContent = <p><s className="dc-was-strike">(none)</s></p>;
    nowContent = <p><mark className="dc-now-mark">[{c.actor.split(/[. ]/)[0]} {c.actor.split(/[. ]/).slice(-1)[0]}]</mark> {seg?.text || c.note}</p>;
  } else if (c.type === "slide_reassignment") {
    wasContent = <p>Slide <s className="dc-was-strike">{c.prior}</s></p>;
    nowContent = <p>Slide <mark className="dc-now-mark">{c.next}</mark> — {c.note}</p>;
  } else if (c.type === "speaker_reassignment") {
    wasContent = <p>Speaker: <s className="dc-was-strike">{c.prior}</s></p>;
    nowContent = <p>Speaker: <mark className="dc-now-mark">{c.next}</mark></p>;
  } else if (c.type === "annotation_add") {
    wasContent = <p><s className="dc-was-strike">(no annotation)</s></p>;
    nowContent = <p>Marked as <mark className="dc-now-mark">{c.next}</mark> — {c.note}</p>;
  } else {
    wasContent = <p style={{ color: "var(--fg2)" }}>—</p>;
    nowContent = <p>{c.note}</p>;
  }

  const timeRange = seg ? `${fmtTime(seg.start)}–${fmtTime(seg.end)}` : "—";

  return (
    <article className={`decision-card ${isActive ? "is-active" : ""}`} onClick={() => seg && onSegmentClick && onSegmentClick(seg.id)}>
      <header className="decision-card__head">
        <span className="decision-card__time">{timeRange}</span>
        <span className={`decision-card__pill decision-card__pill--${pill.tone}`}>{pill.label}</span>
        <span className="decision-card__pill decision-card__pill--export">export</span>
        <span className="decision-card__actor">
          <strong>{c.actor.toLowerCase().replace(/[. ]+/g, "")}</strong> · {new Date(c.t).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: true })}
        </span>
      </header>
      <div className="decision-card__slidechip">{slide?.title || `Segment ${c.seg}`}</div>
      <div className="decision-card__panel decision-card__panel--was">
        <span className="decision-card__lbl">WAS</span>
        {wasContent}
      </div>
      <div className="decision-card__panel decision-card__panel--now">
        <span className="decision-card__lbl">NOW</span>
        {nowContent}
      </div>
    </article>
  );
}

// ── Audit ledger table (shared) ────────────────────────────
function AuditLedger({ compact = false, filter = "all" }) {
  const correctionTypeLabel = {
    text_edit: { label: "text_edit", chip: "red", note: "dirties text · flips has_user_override" },
    chat_insert: { label: "chat_insert", chip: "blue", note: "NON-dirty · preserves flags" },
    chat_edit: { label: "chat_edit", chip: "blue", note: "NON-dirty · preserves flags" },
    chat_remove: { label: "chat_remove", chip: "blue", note: "NON-dirty · preserves flags" },
    poll_insert: { label: "poll_insert", chip: "gold", note: "NON-dirty · preserves flags" },
    poll_remove: { label: "poll_remove", chip: "gold", note: "NON-dirty · preserves flags" },
    slide_reassignment: { label: "slide_reassignment", chip: "amber", note: "NON-dirty · preserves flags" },
    speaker_reassignment: { label: "speaker_reassignment", chip: "amber", note: "NON-dirty · preserves flags" },
    mark_reviewed: { label: "mark_reviewed", chip: "green", note: "NON-dirty · preserves flags" },
    unmark_reviewed: { label: "unmark_reviewed", chip: "green", note: "NON-dirty · preserves flags" },
    annotation_add: { label: "annotation_add", chip: "blue", note: "NON-dirty · preserves flags" },
    annotation_remove: { label: "annotation_remove", chip: "blue", note: "NON-dirty · preserves flags" },
  };
  let rows = MIC_DATA.CORRECTIONS.slice().reverse();
  if (filter !== "all") rows = rows.filter((r) => r.type === filter);
  return (
    <div className="audit-ledger">
      <div className="audit-row audit-row--head">
        <div>Time (UTC)</div>
        <div>Type</div>
        <div>Segment</div>
        <div>Actor</div>
        <div>Delta</div>
        <div>Note</div>
      </div>
      {rows.map((c) => {
        const tl = correctionTypeLabel[c.type] || { label: c.type, chip: "ghost", note: "" };
        return (
          <div key={c.id} className="audit-row">
            <div className="t">{new Date(c.t).toISOString().replace("T", " ").replace(/\..*$/, "")}</div>
            <div><span className={`chip chip--${tl.chip}`}><span className="chip__dot" /> {tl.label}</span></div>
            <div className="seg" onClick={() => navigate(`/e/se_001`)} style={{ cursor: "pointer" }}>{c.seg}</div>
            <div className="actor">{c.actor}</div>
            <div className="delta">
              {c.prior ? <s>{c.prior}</s> : null}
              {c.next ? <b>{c.next}</b> : null}
              {!c.prior && !c.next ? <span style={{ color: "var(--fg2)" }}>—</span> : null}
            </div>
            <div className="note">{c.note || tl.note}</div>
          </div>
        );
      })}
    </div>
  );
}

// ── Standalone audit route — Word Track Changes (v7) ───────
function AuditRoute({ id }) {
  const session = id ? MIC_DATA.SESSIONS.find((s) => s.id === id) : null;
  const [filter, setFilter] = useState("all");
  const stats = useMemo(() => {
    const out = {};
    MIC_DATA.CORRECTIONS.forEach((c) => { out[c.type] = (out[c.type] || 0) + 1; });
    return out;
  }, []);

  const types = [
    { id: "all", label: "All types" },
    { id: "text_edit", label: "text_edit" },
    { id: "chat_insert", label: "chat_insert" },
    { id: "chat_edit", label: "chat_edit" },
    { id: "poll_insert", label: "poll_insert" },
    { id: "slide_reassignment", label: "slide_reassignment" },
    { id: "speaker_reassignment", label: "speaker_reassignment" },
    { id: "mark_reviewed", label: "mark_reviewed" },
    { id: "annotation_add", label: "annotation_add" },
  ];

  return (
    <main className="page" data-screen-label="Audit / Word Track Changes">
        <div className="page-eyebrow">
          <Link to="/sessions">Sessions</Link><span className="sep">/</span>
          {session ? <><Link to={`/e/${session.id}`}>{session.id}</Link><span className="sep">/</span></> : null}
          <span>Audit · Word Track Changes (v7)</span>
        </div>
        <h1 className="page-title">Word Track Changes</h1>
        <p className="page-desc">
          Every correction is a row. Lineage is append-only — no destructive edits at rest.
          Filter by type, replay from any point, jump to the segment in the editor.
        </p>
        <div className="kpi-row">
          <div className="kpi"><div className="kpi__label">Total Corrections</div><div className="kpi__value">{MIC_DATA.CORRECTIONS.length}</div></div>
          <div className="kpi"><div className="kpi__label">Text Edits (dirty)</div><div className="kpi__value" style={{ color: "var(--color-red)" }}>{stats.text_edit || 0}</div><div className="kpi__delta kpi__delta--down">flips has_user_override</div></div>
          <div className="kpi"><div className="kpi__label">Non-dirty Corrections</div><div className="kpi__value" style={{ color: "var(--color-green)" }}>{MIC_DATA.CORRECTIONS.length - (stats.text_edit || 0)}</div><div className="kpi__delta">flag colors preserved</div></div>
          <div className="kpi"><div className="kpi__label">Distinct Actors</div><div className="kpi__value">{new Set(MIC_DATA.CORRECTIONS.map((c) => c.actor)).size}</div></div>
        </div>

        <div className="toolbar">
          <div className="filter-chip-row">
            {types.map((t) => (
              <button key={t.id}
                className={`chip ${filter === t.id ? "chip--solid" : ""}`}
                onClick={() => setFilter(t.id)}
                style={{ cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                {t.label}
                <span style={{ opacity: 0.7 }}>· {t.id === "all" ? MIC_DATA.CORRECTIONS.length : (stats[t.id] || 0)}</span>
              </button>
            ))}
          </div>
          <button className="btn btn--secondary" style={{ marginLeft: "auto" }} data-test-id="audit-wtc-export-jsonl" onClick={() => { downloadBlob(MIC_DATA.CORRECTIONS.map((c) => JSON.stringify(c)).join("\n") + "\n", "audit.jsonl", "application/x-ndjson"); toast.push("Audit JSONL exported", { tone: "ok" }); }}><Icon name="download" /> Export JSONL</button>
        </div>

        <AuditLedger filter={filter} />

        <div className="card" style={{ marginTop: 22 }}>
          <div className="card__header"><h3>L1 — has_user_override Invariant</h3><span className="chip chip--green"><Icon name="check" size={10} /> 11/11 types pass</span></div>
          <div className="card__body">
            <p style={{ margin: 0, fontSize: 13, color: "var(--fg2)", lineHeight: 1.6 }}>
              Snapshot test verifies that <strong>only</strong> <code>text_edit</code> flips <code>has_user_override</code> to <code>true</code>.
              The other ten correction types — chat/poll insert/edit/remove, slide/speaker reassignment, mark_reviewed, annotation_add/remove —
              preserve all AI flag colors (drift / uncertain / low_confidence) on the affected segment.
              This was production-broken twice in v3.x (PR #33, Phase 8b) and is now structurally impossible.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8, marginTop: 14 }}>
              {["text_edit","chat_insert","chat_edit","chat_remove","poll_insert","poll_remove","slide_reassignment","speaker_reassignment","mark_reviewed","unmark_reviewed","annotation_add","annotation_remove"].map((t) => (
                <div key={t} style={{ padding: "8px 10px", background: "var(--surface-bg)", borderRadius: 6, border: "1px solid var(--border-subtle)", fontSize: 11.5, fontFamily: "var(--font-mono)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{t}</span>
                  <span style={{ color: t === "text_edit" ? "var(--color-red)" : "var(--color-green)", fontWeight: 700, fontSize: 10 }}>
                    {t === "text_edit" ? "→ flips" : "preserves"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
  );
}

window.DiscrepanciesPane = DiscrepanciesPane;
window.AuditTabInline = AuditTabInline;
window.AuditLedger = AuditLedger;
window.AuditRoute = AuditRoute;
