/* eslint-disable no-undef */
// Session Detail route — /s/:id
// The page operators land on between Sessions list and the Editor.
// Mirrors the real-app structure: KPIs · downloads · stage assignments ·
// publishing links · session files · timeline · segment-by-segment widgets.

function SessionDetailRoute({ id }) {
  const session = MIC_DATA.SESSIONS.find((s) => s.id === id) || MIC_DATA.SESSIONS[0];
  const stages = MIC_DATA.SOP_STAGES;
  const segments = MIC_DATA.SEGMENTS;
  const slides = MIC_DATA.SLIDES;
  const segmentsBySlide = useMemo(() => {
    const m = new Map();
    slides.forEach((sl) => m.set(sl.id, []));
    segments.forEach((s) => { if (s.slide_id) m.get(s.slide_id)?.push(s); });
    return m;
  }, [segments, slides]);

  const stageAssignments = [
    { stage: "copy_draft", who: "(unassigned)",                   group: false, faded: true },
    { stage: "medical",    who: "V@V · Heather Howell",            group: false },
    { stage: "copy_final", who: "Main Contact · Ruth Schoonover",  group: false },
    { stage: "cms",        who: "Content Team (default)",          group: true  },
    { stage: "captions",   who: "Content Team",                    group: false },
    { stage: "qa",         who: "Content Team (default)",          group: true  },
  ];

  const sessionFiles = [
    { name: "Slides",            present: true,  desc: "Slides extracted — you can replace or append a new deck.", icon: "slide" },
    { name: "Chat log",          present: true,  desc: "Chat present — uploading new chat replaces existing messages.", icon: "message" },
    { name: "Session manifest",  present: true,  desc: "Manifest present — you can use a new one or keep current.", icon: "doc" },
    { name: "Speaker bios",      present: false, desc: "Without bios, speaker credentials won't render in the export.", icon: "user" },
  ];

  const publishingLinks = ["Zoom recording", "Slides", "Podbean", "VINcast", "Intranet", "Session page"];
  const downloads = [
    { kind: "Word Document",  ext: ".docx", desc: "Macro-compatible transcript with slide codes and speaker labels." },
    { kind: "Captions",       ext: ".srt",  desc: "SubRip subtitle file for Wistia or video player." },
    { kind: "Plain Text",     ext: ".txt",  desc: "Simple text for email, forum paste, or quick reference." },
    { kind: "Word Macro",     ext: ".zip",  desc: "One-time install. Developer → Visual Basic → Import." },
  ];

  // Build review queue from needs_review segments
  const reviewQueue = segments.filter((s) => s.needs_review).slice(0, 10).map((s, i) => ({
    id: `g${95 + i}`,
    seg: s.id,
    conf: s.confidence === "low" ? 0 : 0,
    preview: s.text.slice(0, 80) + "…",
    assignee: "unassigned",
  }));

  const totalSegs = session.segs || segments.length;
  const segConfList = Array.from({ length: Math.min(31, totalSegs) }, (_, i) => {
    const pct = 75 + ((i * 7) % 25);
    const slideId = slides[i % slides.length]?.id;
    return { n: i + 1, conf: pct, ok: pct >= 80 ? "ok" : "warn", slideColor: slideAccent(slideId) };
  });

  // 2026-06-04 stakeholder direction: Chat Participants tally surfaces on
  // the session detail view (NOT the editor view). Aggregates the chat
  // stream by author. Backend endpoint:
  //   GET /v1/sessions/{id}/chat-participants
  // Shape: [{ speaker, message_count, first_seen_ms, last_seen_ms }]
  // Sample data approximating the original VIN Rounds Zoom chat shape.
  const chatParticipants = [
    { speaker: "Heather Howell (she/her)", message_count: 6 },
    { speaker: "Gaelle Roth",              message_count: 5 },
    { speaker: "Teresa Bousquet",          message_count: 4 },
    { speaker: "Gretchen Gerber",          message_count: 4 },
    { speaker: "Giavanna Smith",           message_count: 4 },
    { speaker: "Kathy Oh",                 message_count: 2 },
    { speaker: "Claire Gossett",           message_count: 2 },
  ];
  const totalChatMessages = chatParticipants.reduce((sum, p) => sum + p.message_count, 0);

  return (
    <main className="page" data-screen-label={`Session Detail / ${session.id}`}>
      <div className="page-eyebrow">
        <Link to="/sessions">Sessions</Link>
        <span className="sep">/</span>
        <code style={{ fontFamily: "var(--font-mono)", color: "var(--fg-link)" }}>{session.code || session.id}</code>
      </div>

      {/* Header strip */}
      <div className="sd-header">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 6 }}>
            <span className="chip chip--green"><Icon name="check" size={10} /> Content ready</span>
            <span className="chip chip--ghost">{session.code || session.id}</span>
          </div>
          <h1 className="sd-header__title">{session.title}</h1>
          <p className="sd-header__sub">INTERIM: {session.title}</p>
        </div>
        <div className="sd-header__actions">
          <span className="chip chip--amber"><span className="chip__dot" /> {session.needsReviewCount || 0} to review</span>
          <span className="chip chip--green"><span className="chip__dot" /> {session.alignment || 100}% aligned</span>
          <Link to={`/e/${session.id}/sop`} className="btn btn--secondary"><Icon name="branch" /> Workflow</Link>
          <Link to={`/e/${session.id}/audit`} className="btn btn--secondary"><Icon name="history" /> Audit</Link>
          <Link to={`/e/${session.id}`} className="btn btn--primary"><Icon name="edit" /> Open Editor</Link>
        </div>
      </div>

      <div className="sd-grid">
        {/* Left column: session meta */}
        <div className="sd-meta">
          <div className="sd-meta__code">{session.code || session.id}</div>
          <h2 className="sd-meta__title">{session.title}</h2>
          <p className="sd-meta__sub">INTERIM: {session.title}</p>
          <div className="sd-meta__tags">
            <span className="chip chip--ghost" style={{ textTransform: "uppercase", letterSpacing: ".06em", fontSize: 10 }}>CE Broker 20-1341518</span>
            <span className="chip chip--blue" style={{ fontSize: 10 }}>AEMV</span>
            <span className="chip chip--blue" style={{ fontSize: 10 }}>Behave/Welfare</span>
            <span className="chip chip--blue" style={{ fontSize: 10 }}>Sm Mam Exotic</span>
          </div>

          {/* Downloads — compact list under session meta */}
          <div className="sd-meta__downloads">
            <div className="sd-meta__downloads-head">Downloads</div>
            {downloads.map((d) => (
              <button key={d.ext} className="sd-meta__download" data-test-id={`sd-download-${d.ext.slice(1)}`} title={d.desc} onClick={() => wired.download(d.ext.slice(1), session.code || session.id)}>
                <Icon name="download" size={12} />
                <span className="sd-meta__download-kind">{d.kind}</span>
                <code className="sd-meta__download-ext">{d.ext}</code>
              </button>
            ))}
          </div>
        </div>

        {/* Center: KPIs + AI mode */}
        <div className="sd-center">
          <div className="sd-kpis">
            <div className="kpi"><div className="kpi__label">Segments</div><div className="kpi__value">{totalSegs}</div><div className="kpi__delta" style={{ color: "var(--fg2)" }}>transcript blocks</div></div>
            <div className="kpi"><div className="kpi__label">Avg Confidence</div><div className="kpi__value" style={{ color: session.avgConf < 75 ? "var(--color-amber)" : "var(--color-navy)" }}>{session.avgConf || 0}%</div><div className="kpi__delta" style={{ color: "var(--fg2)" }}>across all segments</div></div>
            <div className="kpi"><div className="kpi__label">Words</div><div className="kpi__value">{(session.words || 0).toLocaleString()}</div><div className="kpi__delta" style={{ color: "var(--fg2)" }}>total spoken</div></div>
            <div className="kpi"><div className="kpi__label">Coverage</div><div className="kpi__value">{session.coverage || "—"}</div><div className="kpi__delta" style={{ color: "var(--fg2)" }}>slides assigned</div></div>
            <div className="kpi"><div className="kpi__label">Duration</div><div className="kpi__value">{session.duration}</div><div className="kpi__delta" style={{ color: "var(--fg2)" }}>total runtime</div></div>
          </div>

          <div className="sd-row-2">
            <div className="card">
              <div className="card__header"><h3>Alignment</h3></div>
              <div className="card__body" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                <div>
                  <div style={{ fontSize: 36, fontWeight: 800, color: "var(--color-green)", lineHeight: 1 }}>{session.alignment || 100}%</div>
                  <div style={{ fontSize: 11, color: "var(--fg2)", marginTop: 4, textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 700 }}>Auto-aligned</div>
                </div>
                <div>
                  <div style={{ fontSize: 36, fontWeight: 800, color: "var(--fg1)", lineHeight: 1 }}>{totalSegs}</div>
                  <div style={{ fontSize: 11, color: "var(--fg2)", marginTop: 4, textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 700 }}>Sections</div>
                </div>
              </div>
            </div>
            <div className="card sd-aimode">
              <div className="card__header"><h3>AI Mode — Gemini cleaned filler</h3></div>
              <div className="card__body">
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span className="chip chip--blue" style={{ fontSize: 11 }}>um/uh/er/ah removed</span>
                  <span className="chip chip--blue" style={{ fontSize: 11 }}>Verbatim otherwise</span>
                </div>
                <p style={{ fontSize: 12, color: "var(--fg2)", marginTop: 10, lineHeight: 1.5 }}>
                  Three-tier normalization: <strong>raw</strong> → <strong>verbatim-minus-fillers</strong> (default export) → <strong>key points</strong> (optional).
                </p>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card__header">
              <h3 style={{ color: "var(--color-amber)" }}><Icon name="alert" size={12} /> Session files — attention</h3>
              <span className="chip chip--amber" style={{ fontSize: 10 }}>1 missing</span>
            </div>
            <div className="card__body" style={{ padding: 0 }}>
              {sessionFiles.map((f) => (
                <div key={f.name} className="sd-file">
                  <div className="sd-file__icon"><Icon name={f.icon} size={16} /></div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                      <strong style={{ fontSize: 13, color: "var(--fg1)" }}>{f.name}</strong>
                      {f.present
                        ? <span className="chip chip--green" style={{ fontSize: 9 }}>PRESENT</span>
                        : <span className="chip chip--amber" style={{ fontSize: 9 }}>MISSING</span>}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--fg2)" }}>{f.desc}</div>
                  </div>
                  <button className={`btn btn--sm ${f.present ? "btn--secondary" : "btn--primary"}`} data-test-id={`sd-file-${f.name.replace(/\s/g, "_")}`} onClick={() => { wired.toastInfo(`${f.present ? "Update" : "Add"} ${f.name} — file picker (mock)`); auditLog.log("You", "file", `${f.present ? "Updated" : "Added"} ${f.name}`); }}>{f.present ? "Update" : "Add"}</button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: stage assignments + publishing */}
        <div className="sd-right">
          <div className="card">
            <div className="card__header">
              <h3>Stage Assignments</h3>
              <select className="btn btn--secondary btn--sm" style={{ paddingRight: 24, fontSize: 11 }}>
                <option>Type: default</option>
                <option>Type: lecture</option>
                <option>Type: rounds</option>
              </select>
            </div>
            <div className="card__body" style={{ padding: 0 }}>
              {stageAssignments.map((a) => {
                const s = stages.find((x) => x.id === a.stage);
                if (!s) return null;
                return (
                  <div key={a.stage} className="sd-stage-row">
                    <div>
                      <div className="sd-stage-row__name">{s.name}</div>
                      <div className={`sd-stage-row__who ${a.faded ? "is-faded" : ""}`}>
                        {a.group ? <span style={{ fontSize: 10, color: "var(--fg2)", marginRight: 4, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase" }}>Group:</span> : null}
                        {a.who}
                      </div>
                    </div>
                    <button className="btn btn--ghost btn--icon btn--sm" data-test-id={`sd-reassign-${a.stage}`} title="Reassign" onClick={() => wired.reassignStage(s.name)}><Icon name="edit" /></button>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="card__header"><h3>Publishing Links</h3></div>
            <div className="card__body" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {publishingLinks.map((p) => (
                <button key={p} className="chip" data-test-id={`sd-pub-${p.replace(/\s/g, "_")}`} style={{ cursor: "pointer", background: "var(--surface-bg)", borderColor: "var(--border-subtle)", padding: "5px 12px" }} onClick={() => { wired.toastInfo(`${p} — link saved`); auditLog.log("You", "publishing", `Updated ${p} link`); }}>
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Timeline bar */}
      <div className="sd-timeline-card">
        <div className="sd-timeline-card__head">
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".12em", textTransform: "uppercase", color: "var(--fg2)" }}>
            Timeline · {session.duration} · segments by slide color
          </span>
        </div>
        <div className="sd-timeline">
          {slides.map((sl, i) => {
            const segs = segmentsBySlide.get(sl.id);
            if (!segs || !segs.length) return null;
            const total = MIC_DATA.TOTAL_DURATION;
            const x1 = (segs[0].start / total) * 100;
            const w  = ((segs[segs.length - 1].end - segs[0].start) / total) * 100;
            return (
              <div key={sl.id} className="sd-timeline__seg"
                   style={{ left: `${x1}%`, width: `${Math.max(0.5, w)}%`, background: slideAccent(sl.id) }}
                   title={`${sl.title} · ${segs.length} segs`} />
            );
          })}
        </div>
        <div className="sd-timeline__axis">
          <span>0:00</span>
          <span>{session.duration}</span>
        </div>
      </div>

      {/* Segment-level widgets row */}
      <div className="sd-widgets">
        <div className="card">
          <div className="card__header"><h3>Segment Confidence</h3><span className="chip chip--ghost" style={{ fontSize: 10 }}>1–{segConfList.length}</span></div>
          <div className="card__body" style={{ padding: 0 }}>
            {segConfList.map((s) => (
              <div key={s.n} className="sd-confrow">
                <span style={{ width: 22, fontSize: 11, color: "var(--fg2)", fontFamily: "var(--font-mono)" }}>{s.n}</span>
                <span style={{ flex: 1, fontSize: 12, color: "var(--fg1)" }}>{s.conf}%</span>
                <Icon name="check" size={11} className={s.ok === "ok" ? "" : ""} />
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.slideColor }} />
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card__header"><h3>Slide Assignment</h3><span className="chip chip--ghost" style={{ fontSize: 10 }}>{slides.length} slides</span></div>
          <div className="card__body" style={{ padding: 0 }}>
            {slides.slice(0, 16).map((sl, i) => {
              const segs = segmentsBySlide.get(sl.id);
              return (
                <div key={sl.id} className="sd-slideassign">
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: slideAccent(sl.id), flexShrink: 0 }} />
                  <span style={{ width: 24, fontSize: 11, color: "var(--fg2)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>{String(sl.n).padStart(2, "0")}</span>
                  <span style={{ flex: 1, fontSize: 12, color: "var(--fg1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {sl.title.replace(/^Title — /, "").replace(/^Case Study \d+ — /, "")}
                  </span>
                  <span style={{ fontSize: 10.5, color: "var(--fg2)", fontFamily: "var(--font-mono)" }}>{segs?.length || 0} segs</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card">
          <div className="card__header"><h3>Review Queue</h3><span className="chip chip--amber" style={{ fontSize: 10 }}>{reviewQueue.length} pending</span></div>
          <div className="card__body" style={{ padding: 0, maxHeight: 380, overflowY: "auto" }}>
            {reviewQueue.length === 0
              ? <div style={{ padding: 18, fontSize: 12, color: "var(--fg2)", textAlign: "center" }}>No segments flagged for review.</div>
              : reviewQueue.map((r) => (
                <div key={r.id} className="sd-reviewrow">
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-amber)", fontWeight: 700 }}>{r.id} · 0% confidence</span>
                    <span style={{ fontSize: 10, color: "var(--fg2)", fontStyle: "italic" }}>{r.assignee}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--fg1)", lineHeight: 1.4, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {r.preview}
                  </div>
                </div>
              ))}
          </div>
        </div>

        <div className="card" data-test-id="sd-chat-participants">
          <div className="card__header"><h3>Chat Participants</h3><span className="chip chip--ghost" style={{ fontSize: 10 }}>{totalChatMessages} msgs</span></div>
          <div className="card__body" style={{ padding: 0, maxHeight: 380, overflowY: "auto" }}>
            {chatParticipants.length === 0
              ? <div style={{ padding: 18, fontSize: 12, color: "var(--fg2)", textAlign: "center" }}>No chat yet.</div>
              : chatParticipants.map((p) => (
                <div key={p.speaker} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 12px", borderBottom: "1px solid var(--border)" }}>
                  <span style={{ flex: 1, fontSize: 12, color: "var(--fg1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.speaker}</span>
                  <span style={{ fontSize: 11, color: "var(--fg2)", fontFamily: "var(--font-mono)", fontWeight: 700 }}>{p.message_count}</span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </main>
  );
}

window.SessionDetailRoute = SessionDetailRoute;
