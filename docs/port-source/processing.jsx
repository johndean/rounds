/* eslint-disable no-undef */
// Processing route — /p/:id  (8-hop pipeline trace)
// Also exports GCS QA route for /gcs.

function ProcessingRoute({ id }) {
  const session = MIC_DATA.SESSIONS.find((s) => s.id === id) || MIC_DATA.SESSIONS.find((s) => s.status === "processing") || MIC_DATA.SESSIONS[0];
  // Use CSS-animated elapsed (per §15.9), NOT 1Hz reactive update.
  const hops = [
    { n: 1, name: "Asset Upload",           desc: "Audio + slide deck received from presenter",     status: "done",     t: "0:00:32" },
    { n: 2, name: "Media Probe",            desc: "FFmpeg probe · duration / channels / sample rate", status: "done",     t: "0:00:11" },
    { n: 3, name: "GCS Persist",            desc: "Upload to gs://vin-transcripts/se_007/...",       status: "done",     t: "0:01:48" },
    { n: 4, name: "STT (Google)",           desc: "Streaming recognition · 47 min audio",            status: "done",     t: "0:08:14" },
    { n: 5, name: "Gemini Reconstruction",  desc: "Verbatim-minus-fillers · 3-tier normalization",   status: "running",  t: "0:03:42 …" },
    { n: 6, name: "Slide Alignment",        desc: "Segment ↔ slide_id assignment",                   status: "pending",  t: "—" },
    { n: 7, name: "Discrepancy Classification", desc: "STT vs base_text · server-side LCS",          status: "pending",  t: "—" },
    { n: 8, name: "Ready for Edit",         desc: "Session graduates to Prep stage",                 status: "pending",  t: "—" },
  ];
  return (
    <React.Fragment>
    <main className="page" data-screen-label="Processing">
        <div className="page-eyebrow">
          <Link to="/sessions">Sessions</Link><span className="sep">/</span>
          <span>Processing · {session.id}</span>
        </div>
        <h1 className="page-title">{session.title}</h1>
        <p className="page-desc">
          Session is ingesting. The 8-hop pipeline trace below mirrors the GCS QA surface (G1–G14). Editor opens automatically when hop 8 completes.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 18 }}>
          <div className="processing-trace">
            {hops.map((h) => (
              <div key={h.n} className="trace-hop">
                <div className="trace-hop__n">G{h.n}</div>
                <div>
                  <div className="trace-hop__name">{h.name}</div>
                  <div className="trace-hop__desc">{h.desc}</div>
                </div>
                <div>
                  {h.status === "done" && <div className="progress progress--green"><span style={{ width: "100%" }} /></div>}
                  {h.status === "running" && <div className="progress progress--blue"><span style={{ width: "55%", animation: "indet 2s linear infinite" }} /></div>}
                  {h.status === "pending" && <div className="progress"><span style={{ width: "0%" }} /></div>}
                </div>
                <div className="trace-hop__t">{h.t}</div>
                <div>
                  {h.status === "done"    && <span className="chip chip--green"><Icon name="check" size={10} /> done</span>}
                  {h.status === "running" && <span className="chip chip--blue"><Icon name="spinner" size={10} /> running</span>}
                  {h.status === "pending" && <span className="chip chip--ghost"><span className="chip__dot" /> queued</span>}
                </div>
              </div>
            ))}
          </div>
          <div>
            <div className="card">
              <div className="card__header"><h3>Pipeline Health</h3><span className="dot" style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--color-green)", boxShadow: "0 0 6px rgba(0,125,97,0.6)" }} /></div>
              <div className="card__body" style={{ fontSize: 12.5, color: "var(--fg2)", lineHeight: 1.6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Queue depth</span><strong style={{ color: "var(--fg1)", fontFamily: "var(--font-mono)" }}>2</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Avg STT time</span><strong style={{ color: "var(--fg1)", fontFamily: "var(--font-mono)" }}>0.18× realtime</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Avg Gemini time</span><strong style={{ color: "var(--fg1)", fontFamily: "var(--font-mono)" }}>0.07× realtime</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span>Dead-letter</span><strong style={{ color: "var(--color-green)", fontFamily: "var(--font-mono)" }}>0</strong>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Last failure</span><strong style={{ color: "var(--fg1)", fontFamily: "var(--font-mono)" }}>—</strong>
                </div>
              </div>
            </div>
            <div className="card" style={{ marginTop: 14 }}>
              <div className="card__header"><h3>Operator Actions</h3></div>
              <div className="card__body" style={{ display: "grid", gap: 6 }}>
                <button className="btn btn--secondary btn--sm" data-test-id="proc-open-gcs" onClick={() => wired.openGCS(session.id)}><Icon name="external" /> Open in GCS console</button>
                <button className="btn btn--secondary btn--sm" data-test-id="proc-download-stt" onClick={() => wired.download("stt-raw", session.id)}><Icon name="download" /> Download raw STT</button>
                <button className="btn btn--ghost btn--sm" data-test-id="proc-cancel" style={{ color: "var(--color-red)" }} onClick={() => wired.cancelIngestion(session.id)}><Icon name="x" /> Cancel ingestion</button>
              </div>
            </div>
          </div>
        </div>
        <style dangerouslySetInnerHTML={{ __html: "@keyframes indet { 0% { transform: translateX(-30%) } 100% { transform: translateX(80%) } }" }} />
      </main>
    </React.Fragment>
  );
}

// ── GCS QA route — /gcs ────────────────────────────────────
function GcsRoute() {
  const checks = [
    { id: "G1",  name: "Asset bucket exists",        ok: true,  ms: 12 },
    { id: "G2",  name: "Object ACLs (uniform)",      ok: true,  ms: 22 },
    { id: "G3",  name: "Lifecycle policy applied",    ok: true,  ms: 8  },
    { id: "G4",  name: "Retention lock present",      ok: true,  ms: 14 },
    { id: "G5",  name: "KMS key rotation < 90d",      ok: true,  ms: 36 },
    { id: "G6",  name: "Audit log streaming",         ok: true,  ms: 24 },
    { id: "G7",  name: "Pub/Sub subscription live",   ok: true,  ms: 18 },
    { id: "G8",  name: "STT credentials valid",       ok: true,  ms: 41 },
    { id: "G9",  name: "Gemini quota healthy",        ok: true,  ms: 28 },
    { id: "G10", name: "DLQ depth < threshold",       ok: true,  ms: 11 },
    { id: "G11", name: "Backup snapshot < 24h",       ok: true,  ms: 9  },
    { id: "G12", name: "Egress region matches policy", ok: true,  ms: 16 },
    { id: "G13", name: "PII redaction sentinel",      ok: false, ms: 52, note: "1 sample required new salt — auto-rotating now" },
    { id: "G14", name: "End-to-end smoke (5 files)",  ok: true,  ms: 1480 },
  ];
  const okCount = checks.filter((c) => c.ok).length;
  return (
    <main className="page" data-screen-label="GCS QA">
        <div className="page-eyebrow"><span>Operations</span><span className="sep">/</span><span>GCS Pipeline QA</span></div>
        <h1 className="page-title">GCS Pipeline QA</h1>
        <p className="page-desc">
          14 checks across the GCS-side ingestion plane. Each check runs on a 5-minute cadence; results stream
          into the audit ledger. Failures trigger PagerDuty after two consecutive misses.
        </p>
        <div className="kpi-row">
          <div className="kpi"><div className="kpi__label">Checks Passing</div><div className="kpi__value" style={{ color: "var(--color-green)" }}>{okCount}/14</div></div>
          <div className="kpi"><div className="kpi__label">Last Sweep</div><div className="kpi__value" style={{ fontSize: 18 }}>00:01:42</div><div className="kpi__delta">cadence 5 min</div></div>
          <div className="kpi"><div className="kpi__label">7-Day Uptime</div><div className="kpi__value">99.98%</div></div>
          <div className="kpi"><div className="kpi__label">Open Pages</div><div className="kpi__value">0</div></div>
        </div>
        <div className="audit-ledger">
          <div className="audit-row audit-row--head" style={{ gridTemplateColumns: "60px 1fr 80px 80px 1fr" }}>
            <div>ID</div><div>Check</div><div>Status</div><div>Latency</div><div>Note</div>
          </div>
          {checks.map((c) => (
            <div key={c.id} className="audit-row" style={{ gridTemplateColumns: "60px 1fr 80px 80px 1fr" }}>
              <div className="seg">{c.id}</div>
              <div className="type">{c.name}</div>
              <div>{c.ok ? <span className="chip chip--green"><Icon name="check" size={10} /> pass</span> : <span className="chip chip--amber"><Icon name="alert" size={10} /> retrying</span>}</div>
              <div className="t">{c.ms} ms</div>
              <div className="note">{c.note || "—"}</div>
            </div>
          ))}
        </div>
      </main>
  );
}

window.ProcessingRoute = ProcessingRoute;
window.GcsRoute = GcsRoute;
