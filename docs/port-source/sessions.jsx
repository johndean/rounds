/* eslint-disable no-undef */
// Sessions list route — /sessions

function SessionsRoute({ filter }) {
  const path = useHashRoute();
  // Parse query params from hash: e.g. "/sessions?stage=medical" or "/sessions?ai=ready"
  const qsParams = useMemo(() => {
    const qIdx = path.indexOf("?");
    if (qIdx < 0) return {};
    const out = {};
    path.slice(qIdx + 1).split("&").forEach((p) => {
      const [k, v] = p.split("=");
      if (k) out[decodeURIComponent(k)] = decodeURIComponent(v || "");
    });
    return out;
  }, [path]);
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState(filter || qsParams.f || "all");
  const [stageFilter, setStageFilter] = useState(qsParams.stage || null);
  const [aiFilter, setAiFilter]       = useState(qsParams.ai || null);
  const [sortBy, setSortBy] = useState("updated");
  const sessions = MIC_DATA.SESSIONS;

  // Re-sync on hash change (e.g. user clicks another pipeline circle)
  useEffect(() => {
    if (qsParams.stage) setStageFilter(qsParams.stage);
    if (qsParams.ai)    setAiFilter(qsParams.ai);
    if (qsParams.f)     setActiveFilter(qsParams.f);
    if (!qsParams.stage && !qsParams.ai && !qsParams.f) {
      setStageFilter(null); setAiFilter(null);
    }
  }, [qsParams.stage, qsParams.ai, qsParams.f]);

  const filtered = useMemo(() => {
    let rows = sessions;
    if (stageFilter) rows = rows.filter((s) => s.stage === stageFilter);
    if (aiFilter)    rows = rows.filter((s) => (s.aiStatus || (s.status === "processing" ? "transcribe" : s.status === "complete" ? "ready" : "ready")) === aiFilter);
    if (activeFilter === "active")     rows = rows.filter((s) => s.status === "active");
    if (activeFilter === "processing") rows = rows.filter((s) => s.status === "processing");
    if (activeFilter === "complete")   rows = rows.filter((s) => s.status === "complete");
    if (activeFilter === "needs")      rows = rows.filter((s) => s.needsReviewCount > 0);
    if (query) {
      const q = query.toLowerCase();
      rows = rows.filter((s) => s.title.toLowerCase().includes(q) || s.presenter.toLowerCase().includes(q));
    }
    return rows;
  }, [sessions, activeFilter, query, stageFilter, aiFilter]);

  const clearStageOrAi = () => {
    setStageFilter(null); setAiFilter(null);
    navigate("/sessions");
  };
  const stageMeta = stageFilter ? MIC_DATA.SOP_STAGES.find((x) => x.id === stageFilter) : null;

  const filters = [
    { id: "all",        label: "All",          count: sessions.length },
    { id: "active",     label: "In Workflow",  count: sessions.filter((s) => s.status === "active").length },
    { id: "needs",      label: "Needs Review", count: sessions.filter((s) => s.needsReviewCount > 0).length },
    { id: "processing", label: "Processing",   count: sessions.filter((s) => s.status === "processing").length },
    { id: "complete",   label: "Published",    count: sessions.filter((s) => s.status === "complete").length },
  ];

  return (
    <main className="page" data-screen-label="Sessions List">
        <div className="page-eyebrow">
          <span>Workspace</span><span className="sep">/</span><span>Sessions</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 20, marginBottom: 8 }}>
          <div>
            <h1 className="page-title">Sessions</h1>
            <p className="page-desc">Continuing-education recordings in the v4 transcription pipeline. Click any row to open the editor, or use the SOP workflow to advance a session through review.</p>
          </div>
          <div className="page-actions">
            <button className="btn btn--secondary" data-test-id="sessions-export" onClick={wired.exportCSV}><Icon name="download" /> Export CSV</button>
            <button className="btn btn--primary" data-test-id="sessions-new-upload" onClick={() => navigate("/upload")}><Icon name="circle-dot" /> New upload</button>
          </div>
        </div>

        {/* KPI strip */}
        <div className="kpi-row" style={{ marginTop: 18 }}>
          <div className="kpi">
            <div className="kpi__label">In Workflow</div>
            <div className="kpi__value">{sessions.filter((s) => s.status === "active").length}</div>
            <div className="kpi__delta">▲ 2 since last week</div>
          </div>
          <div className="kpi">
            <div className="kpi__label">Awaiting Medical Review</div>
            <div className="kpi__value">{sessions.filter((s) => s.stage === "medical").length}</div>
            <div className="kpi__delta kpi__delta--down">▼ 1 since yesterday</div>
          </div>
          <div className="kpi">
            <div className="kpi__label">Open Discrepancies</div>
            <div className="kpi__value">42</div>
            <div className="kpi__delta kpi__delta--down">▼ 11 since this morning</div>
          </div>
          <div className="kpi">
            <div className="kpi__label">Published this Month</div>
            <div className="kpi__value">14</div>
            <div className="kpi__delta">▲ 3 vs Apr</div>
          </div>
        </div>

        <div className="toolbar">
          <div className="search">
            <Icon name="search" />
            <input placeholder="Search by title or presenter…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <div className="filter-chip-row">
            {(stageFilter || aiFilter) ? (
              <span className="chip chip--solid" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                {stageFilter ? <>SOP: <strong>{stageMeta?.name}</strong></> : <>AI: <strong>{aiFilter}</strong></>}
                <button onClick={clearStageOrAi} style={{ background: "transparent", border: "none", color: "inherit", fontSize: 13, cursor: "pointer", padding: 0, marginLeft: 4 }}>×</button>
              </span>
            ) : null}
            {filters.map((f) => (
              <button key={f.id}
                className={`chip ${activeFilter === f.id ? "chip--solid" : ""}`}
                style={{ cursor: "pointer", border: "1px solid var(--border-subtle)" }}
                onClick={() => setActiveFilter(f.id)}>
                {f.label} <span style={{ opacity: 0.7 }}>· {f.count}</span>
              </button>
            ))}
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "var(--fg2)" }}>
            Sort
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="btn btn--secondary btn--sm" style={{ paddingRight: 24 }}>
              <option value="updated">Last updated</option>
              <option value="recorded">Recorded date</option>
              <option value="stage">Stage</option>
              <option value="attendees">Attendees</option>
            </select>
          </div>
        </div>

        <div className="sessions-table" role="table" aria-label="Sessions">
          <div className="sessions-table__row sessions-table__row--head" role="row">
            <div>Code</div>
            <div>Session</div>
            <div>AI Status</div>
            <div>SOP</div>
            <div>Segs</div>
            <div>Created</div>
            <div></div>
          </div>
          {filtered.map((s) => {
            const stage = MIC_DATA.SOP_STAGES.find((x) => x.id === s.stage);
            const route = s.status === "processing" ? `/p/${s.id}` : `/s/${s.id}`;
            const aiStatus = s.status === "processing" ? { label: "Processing", chip: "amber" }
                            : s.status === "complete"   ? { label: "Published",  chip: "green" }
                            : { label: "Ready", chip: "green" };
            return (
              <div
                key={s.id}
                role="row"
                className="sessions-table__row sessions-table__row--body"
                onClick={() => navigate(route)}>
                <div className="sessions-table__code">{s.code || s.id}</div>
                <div>
                  <div className="sessions-table__title">{s.title}</div>
                  <div className="sessions-table__sub">{(s.code || s.id) + (s.status === "processing" ? "_audio.mp3" : "_trim.mp3")}</div>
                </div>
                <div>
                  <span className={`chip chip--${aiStatus.chip}`}><span className="chip__dot" /> {aiStatus.label}</span>
                </div>
                <div><StageBadge id={s.stage} /></div>
                <div className="sessions-table__meta" style={{ fontVariantNumeric: "tabular-nums", fontWeight: 600, color: "var(--fg1)" }}>{s.segs || 0}</div>
                <div className="sessions-table__updated">{s.recorded.replace(/^\d{4}-/, "").replace(/-/, " · ")}</div>
                <div style={{ textAlign: "right" }}>
                  <button className="btn btn--ghost btn--icon btn--sm" data-test-id={`sessions-delete-${s.id}`} title="Delete" onClick={(e) => { e.stopPropagation(); wired.deleteRow(s.code || s.id); }}>
                    <Icon name="x" size={12} />
                  </button>
                </div>
              </div>
            );
          })}
          {filtered.length === 0 ? (
            <div style={{ padding: 36, textAlign: "center", color: "var(--fg2)" }}>No sessions match this filter.</div>
          ) : null}
        </div>
      </main>
  );
}

window.SessionsRoute = SessionsRoute;
