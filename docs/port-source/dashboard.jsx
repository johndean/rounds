/* eslint-disable no-undef */
// Dashboard route — /dashboard
// Production-parity: dual-pipeline, your queue cards, SLA-by-stage,
// jobs queue, storage breakdown, assignment coverage.

function DashboardRoute() {
  const stages = MIC_DATA.SOP_STAGES;
  const [pipelineFilter, setPipelineFilter] = useState("all");
  const [timeRange, setTimeRange] = useState("7d");

  // Top KPI strip — 6 cards w/ sparklines
  const topKpis = [
    { label: "AI Sessions",     value: 19,      sub: "19 ready · 0 processing", spark: [12,14,15,17,16,18,19] },
    { label: "SOP Sessions",    value: 23,      sub: "8-stage workflow",         spark: [18,19,21,20,22,22,23] },
    { label: "Segments",        value: "1,607", sub: <><code>words[]</code> immutable SSOT</>, spark: [800,1020,1190,1310,1420,1530,1607] },
    { label: "Artifacts",       value: 1,       sub: "0 lineage rows",           spark: [0,0,0,0,0,1,1] },
    { label: "CMS Published",   value: 0,       sub: <><code>cms_documents</code> table</>, spark: [0,0,0,0,0,0,0] },
    { label: "Improvement RQs", value: 4,       sub: "0 pending",                spark: [1,2,2,3,4,4,4] },
  ];

  // Your Queue — 3 cards
  const queue = [
    { code: "010525_Lykins",    stage: "copy_final", stageLabel: "Copy Edit (final)", title: "VIN/ARAV Rounds: A Spectacle to Behold",        segs: 100, aligned: true, due: "Due in 2d", status: "Review and lock copy" },
    { code: "040226_Williams",  stage: "medical",    stageLabel: "Medical Review",    title: "Controlled Substances: Addressing Drug Diversion", segs: 56,  aligned: true, due: "Due in 3d", status: "Medical accuracy pass" },
    { code: "010925_Gottlieb",  stage: "copy_draft", stageLabel: "Copy Edit (draft)", title: "VIN/IVAPM Rounds: Chronic Pain",                  segs: 62,  aligned: true, due: "Due in 4d", status: "Apply copy edits" },
  ];

  // Operations KPIs — 6 cards w/ sparklines
  const opsKpis = [
    { label: "Unresolved Discrepancies", value: "1,574", sub: "global review backlog",  spark: [1800,1720,1690,1640,1610,1590,1574], color: "var(--text-accent)" },
    { label: "QA Tasks",                 value: 0,       sub: "0 overdue · 0 passed",   spark: [3,2,4,1,2,1,0] },
    { label: "Storage Used",             value: "3.7 GB", sub: "across all sources",    spark: [2.4,2.7,3.0,3.2,3.4,3.6,3.7] },
    { label: "Avg Processing",           value: "3.9m",  sub: "19 samples",             spark: [4.5,4.4,4.2,4.1,4.0,3.95,3.9] },
    { label: "Avg Feedback",             value: "—",     sub: "0 ratings",              spark: [] },
    { label: "Fusion Runs",              value: 0,       sub: <><code>replay_log</code> table</>, spark: [] },
  ];

  // SLA by stage · dwell time vs target
  const sla = [
    { id: "prep",       label: "Prep",              dAvg: 2.1, target: 3, sess: 17, state: "ok" },
    { id: "copy_draft", label: "Copy Edit (draft)", dAvg: 1.4, target: 2, sess: 1,  state: "ok" },
    { id: "medical",    label: "Medical Review",    dAvg: 3.3, target: 2, sess: 1,  state: "breach" },
    { id: "copy_final", label: "Copy Edit (final)", dAvg: 1.8, target: 2, sess: 3,  state: "ok" },
    { id: "cms",        label: "CMS Published",     dAvg: 0.9, target: 1, sess: 1,  state: "ok" },
    { id: "captions",   label: "Captions",          dAvg: null, target: 1, sess: 0, state: "empty" },
    { id: "qa",         label: "QA",                dAvg: null, target: 1, sess: 0, state: "empty" },
    { id: "complete",   label: "Complete",          dAvg: null, target: 0, sess: 0, state: "empty" },
  ];

  // AI processing pipeline — 7 stages
  const aiPipeline = [
    { id: "upload",     label: "Upload",     code: "UPLOAD",     count: 0,  state: "idle" },
    { id: "transcribe", label: "Transcribe", code: "TRANSCRIBE", count: 0,  state: "idle" },
    { id: "normalize",  label: "Normalize",  code: "NORMALIZE",  count: 0,  state: "idle" },
    { id: "align",      label: "Align",      code: "ALIGN",      count: 0,  state: "idle" },
    { id: "fuse",       label: "Fuse",       code: "FUSE",       count: 0,  state: "idle" },
    { id: "ready",      label: "Ready",      code: "READY",      count: 19, state: "active" },
    { id: "failed",     label: "Failed",     code: "FAILED",     count: 0,  state: "failed" },
  ];

  // SOP pipeline — 8 stages
  const sopPipeline = [
    { id: "prep",       count: 17 },
    { id: "copy_draft", count: 1 },
    { id: "medical",    count: 1, attn: true },
    { id: "copy_final", count: 3 },
    { id: "cms",        count: 1 },
    { id: "captions",   count: 0 },
    { id: "qa",         count: 0 },
    { id: "complete",   count: 0 },
  ];

  // SOP Age Alerts
  const ageAlerts = [
    { title: "Crafting a Neurodivergent Career in Veterinary Practice",                stage: "Prep",       age: "3.4d" },
    { title: "VIN/IVAPM Rounds: Chronic Pain",                                          stage: "Prep",       age: "3.4d" },
    { title: "Controlled Substances, Uncontrolled Access: Addressing Drug Diversion…",  stage: "Prep",       age: "3.4d" },
    { title: "VIN/AEMV Rounds: Exotic Companion Mammal Enrichment and Training",        stage: "CE Final",   age: "3.4d" },
    { title: "VIN/IVAPM Rounds: Chronic Pain",                                          stage: "Medical",    age: "3.4d" },
  ];

  // Correction hotspots (top 5 edited)
  const hotspots = [
    { title: "Session 2026-04-18 14:41",                                                 edits: 16, pct: 100 },
    { title: "VIN/ARAV Rounds: A Spectacle to Behold: Snake Ophthalmology Cas…",          edits: 9,  pct: 56 },
    { title: "Cage-side Radiology Rounds: Various Cases. January 6, 2025",                edits: 5,  pct: 31 },
    { title: "Tuesday Topic: Understanding Separation-Related Behaviors",                 edits: 3,  pct: 19 },
    { title: "Tuesday Topic: Equine Dermatology: Bacterial Dermatitis in the Horse:…",     edits: 2,  pct: 12 },
  ];

  // Storage top sessions
  const storageTop = [
    { title: "VIN/VECCS Rounds: Snake Envenomation Management in Pets",                   size: "364 MB", pct: 100 },
    { title: "VIN/ARAV Rounds: A Spectacle to Behold: Snake Ophthalmology Ca…",            size: "231 MB", pct: 63 },
    { title: "VIN/AEMV Rounds: Exotic Companion Mammal Enrichment and Train…",             size: "228 MB", pct: 62 },
    { title: "Cage-Side Radiology Rounds: Various Cases",                                  size: "217 MB", pct: 59 },
    { title: "Lessons Learned From Human Commercial Labs: HbA1C in Europe",                size: "196 MB", pct: 54 },
  ];

  // Jobs queue · last 24h
  const jobs = [
    { name: "transcribe",  ok: 19, err: 0 },
    { name: "normalize",   ok: 19, err: 0 },
    { name: "align",       ok: 19, err: 0 },
    { name: "fuse",        ok: 19, err: 0 },
    { name: "publish_cms", ok: 0,  err: 0 },
  ];

  // Storage breakdown
  const storage = [
    { name: "Audio (raw)",     hint: "audio/*",   size: "2.84 GB", pct: 100 },
    { name: "Transcripts",     hint: "words[]",   size: "410 MB",  pct: 14 },
    { name: "Slide exports",   hint: "png/pdf",   size: "280 MB",  pct: 10 },
    { name: "Artifacts",       hint: "docx/srt",  size: "110 MB",  pct: 4 },
    { name: "Audit + logs",    hint: "jsonl",     size: "60 MB",   pct: 2 },
  ];

  // Assignment coverage
  const coverage = [
    { name: "Tina Pratt",      role: "Editor",     load: 3, cap: 5 },
    { name: "Heather Howell",  role: "Moderator",  load: 2, cap: 6 },
    { name: "Kelsey Lykins",   role: "Medical",    load: 1, cap: 4 },
  ];

  const typeChips = ["All types", "ARAV", "NAVAS"];
  const greeting = useMemo(() => {
    const h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  }, []);
  const dateLabel = useMemo(() => {
    const d = new Date();
    return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }).toUpperCase();
  }, []);

  return (
    <main className="page dash-page" data-screen-label="Dashboard">
      <div className="dash-header">
        <div>
          <div className="dash-eyebrow">Today · {dateLabel}</div>
          <h1 className="dash-title">{greeting}, Kate</h1>
          <p className="dash-lead">Dual-pipeline system · 23 SOP sessions · 19 AI sessions</p>
        </div>
        <div className="page-actions">
          <button className="btn btn--secondary" data-test-id="dash-filters" onClick={() => wired.toastInfo("Filter panel — coming soon")}><Icon name="filter" /> Filters</button>
          <button className="btn btn--primary" onClick={() => navigate("/upload")}><Icon name="circle-dot" /> New upload</button>
        </div>
      </div>

      {/* Top KPI strip */}
      <div className="dash-kpis dash-kpis--6">
        {topKpis.map((k) => (
          <div key={k.label} className="dash-kpi">
            <div className="dash-kpi__label">{k.label}</div>
            <div className="dash-kpi__value">{k.value}</div>
            <div className="dash-kpi__sub">{k.sub}</div>
            <Sparkline data={k.spark} />
          </div>
        ))}
      </div>

      {/* Your Queue */}
      <section className="dash-section">
        <div className="dash-section__head">
          <span className="dash-section__title">Your Queue</span>
          <span className="dash-section__sub">Assigned to you, ordered by due date</span>
          <Link to="/sessions" className="dash-section__action">View all →</Link>
        </div>
        <div className="dash-queue">
          {queue.map((q) => (
            <div key={q.code} className="dash-queue__card" onClick={() => navigate(`/e/se_001`)}>
              <div className="dash-queue__head">
                <div className="dash-queue__code">{q.code}</div>
                <StageBadge id={q.stage} />
              </div>
              <div className="dash-queue__title">{q.title}</div>
              <div className="dash-queue__meta">
                <span>{q.segs} segs</span>
                <span>·</span>
                <span>Aligned</span>
                <span>·</span>
                <span style={{ color: "var(--text-accent)", fontWeight: 700 }}>{q.due}</span>
              </div>
              <div className="dash-queue__foot">
                <span className="dash-queue__status">{q.status}</span>
                <button className="btn btn--primary btn--sm">Open <Icon name="chevron-right" size={11} /></button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="dash-section">
        <div className="dash-section__head">
          <span className="dash-section__title">Pipeline</span>
          <span className="dash-section__sub">23 sessions · 7 AI stages + 8 SOP stages</span>
          <div className="dash-section__filter">
            {typeChips.map((t) => (
              <button key={t} className={`chip ${pipelineFilter === t ? "chip--solid" : ""}`} onClick={() => setPipelineFilter(t)} style={{ cursor: "pointer" }}>{t}</button>
            ))}
            <button className="chip" style={{ cursor: "pointer", color: "var(--fg2)" }} data-test-id="dash-types-more" onClick={() => wired.toastInfo("Showing 5 more type filters: TTOPIC · VSPN · IVAPM · VVI · AFVF")}>+5</button>
          </div>
        </div>

        <div className="dash-pipeline-card">
          <div className="dash-pipeline-card__eyebrow">Pipeline 1 · AI Processing · <code>session.status</code> · 7 stages</div>
          <div className="dash-pipeline">
            {aiPipeline.map((s, i) => (
              <React.Fragment key={s.id}>
                <button type="button" className="dash-pipe-step" data-test-id={`pipe-ai-${s.id}`} onClick={() => navigate(`/sessions?ai=${s.id}`)}>
                  <div className={`dash-pipe-circle dash-pipe-circle--${s.state} ${s.count > 0 ? "is-populated" : ""}`}>{s.count}</div>
                  <div className="dash-pipe-name">{s.label}</div>
                  <div className="dash-pipe-code">{s.code}</div>
                </button>
                {i < aiPipeline.length - 1 ? <span className="dash-pipe-arrow">›</span> : null}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div className="dash-pipeline-card" style={{ marginTop: 10 }}>
          <div className="dash-pipeline-card__eyebrow">Pipeline 2 · SOP Control Layer · <code>sop_sessions.state</code> · 8 stages</div>
          <div className="dash-pipeline">
            {sopPipeline.map((s, i) => {
              const stage = stages.find((x) => x.id === s.id);
              return (
                <React.Fragment key={s.id}>
                  <button type="button" className="dash-pipe-step" data-test-id={`pipe-sop-${s.id}`} onClick={() => navigate(`/sessions?stage=${s.id}`)}>
                    <div className={`dash-pipe-circle dash-pipe-circle--${s.count > 0 ? "active" : "idle"} ${s.attn ? "is-attn" : ""}`}>{s.count}</div>
                    <div className="dash-pipe-name">{stage?.name}</div>
                    <div className="dash-pipe-code">{stage?.id.toUpperCase()}</div>
                    {s.attn ? <div className="dash-pipe-attn">ATTN</div> : null}
                  </button>
                  {i < sopPipeline.length - 1 ? <span className="dash-pipe-arrow">›</span> : null}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </section>

      {/* System overview */}
      <section className="dash-section dash-section--ops">
        <div className="dash-section__head">
          <div>
            <div className="dash-section__eyebrow">Operations · Workflow Health, Throughput, Storage</div>
            <span className="dash-section__title dash-section__title--big">System overview</span>
          </div>
          <div className="dash-section__filter dash-tabs">
            {["7d", "30d", "90d", "All"].map((t) => (
              <button key={t} className={`dash-tab ${timeRange === t ? "is-active" : ""}`} onClick={() => setTimeRange(t)}>{t}</button>
            ))}
          </div>
        </div>

        <div className="dash-kpis dash-kpis--6">
          {opsKpis.map((k) => (
            <div key={k.label} className="dash-kpi">
              <div className="dash-kpi__label">{k.label}</div>
              <div className="dash-kpi__value" style={k.color ? { color: k.color } : null}>{k.value}</div>
              <div className="dash-kpi__sub">{k.sub}</div>
              <Sparkline data={k.spark} />
            </div>
          ))}
        </div>

        {/* SLA by stage */}
        <div className="dash-sla">
          <div className="dash-sla__head">
            <div className="dash-section__eyebrow">SLA BY STAGE · DWELL TIME VS TARGET</div>
            <div className="dash-sla__legend">
              <span><span className="dot" style={{ background: "var(--color-green)" }} /> on target</span>
              <span><span className="dot" style={{ background: "var(--color-blue)" }} /> at risk</span>
              <span><span className="dot" style={{ background: "var(--color-red)" }} /> breach</span>
            </div>
          </div>
          <div className="dash-sla__grid">
            {sla.map((s) => (
              <div key={s.id} className={`dash-sla__cell dash-sla__cell--${s.state}`}>
                <div className="dash-sla__label">{s.label}</div>
                <div className="dash-sla__value">
                  {s.dAvg != null ? <><strong>{s.dAvg}</strong> <span>d avg</span></> : <strong style={{ color: "var(--fg2)" }}>—</strong>}
                </div>
                <div className="dash-sla__bar"><span style={{ width: s.dAvg ? `${Math.min(100, (s.dAvg / Math.max(s.target, 4)) * 100)}%` : "0%" }} /></div>
                <div className="dash-sla__foot">
                  <span>{s.sess} sess</span>
                  <span>target {s.target}d</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Three-column widget row */}
      <div className="dash-three">
        <div className="dash-widget">
          <div className="dash-widget__head">
            <span className="dash-section__title">SOP Age Alerts</span>
            <span className="dash-section__sub">Oldest first</span>
            <a className="dash-section__action" href="#/sessions">All →</a>
          </div>
          <div className="dash-widget__body">
            {ageAlerts.map((a, i) => (
              <div key={i} className="dash-widget__row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="dash-widget__title">{a.title}</div>
                  <div className="dash-widget__sub">{a.stage}</div>
                </div>
                <div className="dash-widget__age">{a.age}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="dash-widget">
          <div className="dash-widget__head">
            <span className="dash-section__title">Correction Hotspots</span>
            <span className="dash-section__sub">Top 5 edited</span>
            <a className="dash-section__action" href="#/sessions">All →</a>
          </div>
          <div className="dash-widget__body">
            {hotspots.map((h, i) => (
              <div key={i} className="dash-bar-row">
                <div className="dash-bar-row__top">
                  <div className="dash-bar-row__title">{h.title}</div>
                  <div className="dash-bar-row__val">{h.edits} edits</div>
                </div>
                <div className="dash-bar-row__bar"><span style={{ width: `${h.pct}%` }} /></div>
              </div>
            ))}
          </div>
        </div>

        <div className="dash-widget">
          <div className="dash-widget__head">
            <span className="dash-section__title">Storage Top Sessions</span>
            <span className="dash-section__sub">By size</span>
            <a className="dash-section__action" href="#/sessions">All →</a>
          </div>
          <div className="dash-widget__body">
            {storageTop.map((s, i) => (
              <div key={i} className="dash-bar-row">
                <div className="dash-bar-row__top">
                  <div className="dash-bar-row__title">{s.title}</div>
                  <div className="dash-bar-row__val">{s.size}</div>
                </div>
                <div className="dash-bar-row__bar"><span style={{ width: `${s.pct}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom widgets — fully built (no Coming Soon) */}
      <div className="dash-three">
        {/* Jobs Queue */}
        <div className="dash-widget">
          <div className="dash-widget__head">
            <span className="dash-section__title">Jobs Queue</span>
            <span className="dash-section__sub">Last 24h</span>
          </div>
          <div className="dash-widget__body">
            {jobs.map((j) => (
              <div key={j.name} className="dash-jobs-row">
                <span className="dash-jobs-row__name">{j.name}</span>
                <span className="dash-jobs-row__ok">{j.ok} ok</span>
                <span className={`dash-jobs-row__err ${j.err > 0 ? "is-error" : ""}`}>{j.err} err</span>
              </div>
            ))}
          </div>
        </div>

        {/* Storage Breakdown */}
        <div className="dash-widget">
          <div className="dash-widget__head">
            <span className="dash-section__title">Storage Breakdown</span>
          </div>
          <div className="dash-widget__body">
            {storage.map((s) => (
              <div key={s.name} className="dash-bar-row">
                <div className="dash-bar-row__top">
                  <div className="dash-bar-row__title">
                    {s.name} <code style={{ marginLeft: 4, fontSize: 10.5, color: "var(--fg2)" }}>{s.hint}</code>
                  </div>
                  <div className="dash-bar-row__val">{s.size}</div>
                </div>
                <div className="dash-bar-row__bar"><span style={{ width: `${s.pct}%` }} /></div>
              </div>
            ))}
          </div>
        </div>

        {/* Assignment Coverage */}
        <div className="dash-widget">
          <div className="dash-widget__head">
            <span className="dash-section__title">Assignment Coverage</span>
          </div>
          <div className="dash-widget__body">
            {coverage.map((c) => (
              <div key={c.name} className="dash-coverage-row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="dash-coverage-row__name">{c.name}</div>
                  <div className="dash-coverage-row__role">{c.role}</div>
                </div>
                <div className="dash-coverage-row__load">{c.load}/{c.cap}</div>
                <div className="dash-coverage-row__bar"><span style={{ width: `${(c.load / c.cap) * 100}%` }} /></div>
              </div>
            ))}
            <div className="dash-coverage-row dash-coverage-row--unassigned">
              <div style={{ flex: 1 }}>
                <div className="dash-coverage-row__name" style={{ color: "var(--text-accent)" }}>Unassigned</div>
                <div className="dash-coverage-row__role">pool</div>
              </div>
              <div className="dash-coverage-row__load">17</div>
              <a className="dash-section__action" href="#/sessions" style={{ fontSize: 11 }} data-test-id="dash-claim" onClick={(e) => { e.preventDefault(); wired.toastInfo("Claimed 1 unassigned session", "ok"); auditLog.log("You", "claim", "Claimed 1 from unassigned pool"); }}>claim →</a>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function Sparkline({ data }) {
  if (!data || data.length < 2) {
    return <div className="dash-spark dash-spark--empty" />;
  }
  const w = 100, h = 18;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg className="dash-spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

window.DashboardRoute = DashboardRoute;
