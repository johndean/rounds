/* eslint-disable no-undef */
// SOP Workflow route — /e/:id/sop
// Enterprise-grade workflow detail page. Surfaces every signal a reviewer needs
// to act: session identity, stage owners, approvals, acceptance checks, transition
// audit trail, and invariants.

function SopRoute({ id }) {
  const session = MIC_DATA.SESSIONS.find((s) => s.id === id) || MIC_DATA.SESSIONS[0];
  const stages = MIC_DATA.SOP_STAGES;
  const currentIdx = stages.findIndex((s) => s.id === session.stage);
  const current = stages[currentIdx];
  const next = stages[currentIdx + 1];

  // ── Per-stage assignment matrix (deterministic per session) ──
  const stageMeta = useMemo(() => {
    const palette = [
      { assignee: "system",           role: "Auto-ingest",       avatar: "SY", color: "#4D6995" },
      { assignee: "Kate Schultz",     role: "Copy Editor",       avatar: "KS", color: "#0861CE" },
      { assignee: "Dr. Mueller",      role: "Medical Reviewer",  avatar: "PM", color: "#C54644" },
      { assignee: "Ruth Schoonover",  role: "Copy Editor",       avatar: "RS", color: "#B75D04" },
      { assignee: "Content Team",     role: "CMS Owner",         avatar: "CT", color: "#0097A9" },
      { assignee: "Content Team",     role: "Captions",          avatar: "CT", color: "#B9975B" },
      { assignee: "QA Group",         role: "QA",                avatar: "QA", color: "#007D61" },
      { assignee: "—",                role: "—",                 avatar: "—",  color: "#002855" },
    ];
    const out = {};
    stages.forEach((s, i) => { out[s.id] = palette[i] || palette[palette.length - 1]; });
    return out;
  }, [stages]);

  // ── Acceptance check states for current stage ──
  const checkStates = useMemo(() => {
    return current.checks.map((label, i) => {
      const state = (i < current.checks.length - 1) ? "pass" : "fail";
      return {
        label,
        state,
        meta: state === "pass" ? "verified · 12 min ago" : "blocked · awaiting reviewer attestation",
        actor: state === "pass" ? "Kate Schultz" : "—",
      };
    });
  }, [current]);

  const [selectedStage, setSelectedStage] = useState(current.id);
  const view = stages.find((s) => s.id === selectedStage);
  const viewIdx = stages.findIndex((s) => s.id === selectedStage);
  const viewIsCurrent = view.id === current.id;
  const viewIsDone    = viewIdx < currentIdx;
  const viewIsPending = viewIdx > currentIdx;
  const viewMeta = stageMeta[view.id];
  const viewChecks = viewIsCurrent ? checkStates :
    viewIsDone ?
      view.checks.map((l) => ({ label: l, state: "pass", meta: "verified · stage closed", actor: stageMeta[view.id]?.assignee })) :
      view.checks.map((l) => ({ label: l, state: "pending", meta: "queued · prior stage not complete", actor: "—" }));

  const canAdvance = checkStates.every((c) => c.state === "pass");

  // ── Stage transition history (deterministic) ──
  const transitions = useMemo(() => {
    const out = [];
    for (let i = 0; i < currentIdx; i++) {
      const from = stages[i].id;
      const to = stages[i + 1].id;
      const day = 14 - currentIdx + i + 1;
      const hr = 7 + i * 2;
      out.push({
        from, to,
        at: `2026-05-${String(day).padStart(2, "0")}T${String(hr).padStart(2, "0")}:01:00Z`,
        actor: stageMeta[to].assignee,
        actorRole: stageMeta[to].role,
        actorColor: stageMeta[to].color,
        actorAvatar: stageMeta[to].avatar,
        note: i === 0 ? "Auto-advanced — ingest pipeline reported READY." :
              i === 1 ? "Draft copy edit pass complete." :
              i === 2 ? "Medical review attestation signed." :
              "Stage advanced.",
      });
    }
    return out;
  }, [currentIdx, stages, stageMeta]);

  const currentSince = transitions.length
    ? transitions[transitions.length - 1].at
    : `2026-05-14T07:42:00Z`;
  const currentSinceDate = new Date(currentSince);
  const dwellHours = Math.max(1, Math.floor((Date.now() - currentSinceDate.getTime()) / (1000 * 60 * 60)) % 96);

  // ── Approvers per stage (stage owner gets a signature row when stage is complete) ──
  const approvers = stages.slice(0, currentIdx).map((s) => ({
    stage: s,
    by: stageMeta[s.id].assignee,
    role: stageMeta[s.id].role,
    avatar: stageMeta[s.id].avatar,
    color: stageMeta[s.id].color,
    at: transitions.find((t) => t.from === s.id)?.at,
  }));

  // ── Key signals at the top of the page ──
  const completionPct = Math.round((currentIdx / stages.length) * 100);
  const blockers = checkStates.filter((c) => c.state !== "pass").length;

  return (
    <main className="page" data-screen-label="SOP Workflow">
      <div className="page-eyebrow">
        <Link to="/sessions">Sessions</Link><span className="sep">/</span>
        <Link to={`/s/${session.id}`}>{session.code || session.id}</Link><span className="sep">/</span>
        <span>SOP Workflow</span>
      </div>

      {/* ── Session identity header ── */}
      <div className="sop-header">
        <div className="sop-header__left">
          <div className="sop-header__code">{session.code || session.id}</div>
          <h1 className="sop-header__title">{session.title}</h1>
          <div className="sop-header__meta">
            <span><strong>{session.presenter}</strong></span>
            <span className="sep">·</span>
            <span>Recorded {session.recorded}</span>
            <span className="sep">·</span>
            <span>{session.duration}</span>
            <span className="sep">·</span>
            <span>{(session.segs || 0).toLocaleString()} segments · {(session.words || 0).toLocaleString()} words</span>
            <span className="sep">·</span>
            <span>{(session.attendees || 0).toLocaleString()} attendees</span>
          </div>
        </div>
        <div className="sop-header__right">
          <Link to={`/e/${session.id}`} className="btn btn--secondary"><Icon name="chevron-left" /> Back to editor</Link>
          <Link to={`/v/${session.id}`} className="btn btn--ghost"><Icon name="external" /> Viewer</Link>
        </div>
      </div>

      {/* ── Workflow KPI strip ── */}
      <div className="sop-kpis">
        <div className="sop-kpi">
          <div className="sop-kpi__label">Current Stage</div>
          <div className="sop-kpi__value">
            <StageBadge id={current.id} />
          </div>
          <div className="sop-kpi__sub">Stage {current.order} of {stages.length}</div>
        </div>
        <div className="sop-kpi">
          <div className="sop-kpi__label">Assigned to</div>
          <div className="sop-kpi__value sop-kpi__value--avatar">
            <span className="sop-avatar" style={{ background: stageMeta[current.id]?.color }}>{stageMeta[current.id]?.avatar}</span>
            <span style={{ fontWeight: 700, color: "var(--fg1)" }}>{stageMeta[current.id]?.assignee}</span>
          </div>
          <div className="sop-kpi__sub">{stageMeta[current.id]?.role}</div>
        </div>
        <div className="sop-kpi">
          <div className="sop-kpi__label">Dwell in stage</div>
          <div className="sop-kpi__value" style={{ color: dwellHours > 48 ? "var(--color-amber)" : "var(--fg1)" }}>{dwellHours}h</div>
          <div className="sop-kpi__sub">since {currentSinceDate.toISOString().slice(0, 16).replace("T", " ")}</div>
        </div>
        <div className="sop-kpi">
          <div className="sop-kpi__label">Acceptance checks</div>
          <div className="sop-kpi__value">{checkStates.filter((c) => c.state === "pass").length}<span style={{ color: "var(--fg2)", fontWeight: 500, fontSize: 18 }}>/{checkStates.length}</span></div>
          <div className="sop-kpi__sub" style={{ color: blockers ? "var(--color-amber)" : "var(--color-green)" }}>{blockers ? `${blockers} blocker${blockers === 1 ? "" : "s"}` : "all passing"}</div>
        </div>
        <div className="sop-kpi">
          <div className="sop-kpi__label">Pipeline progress</div>
          <div className="sop-kpi__value">{completionPct}%</div>
          <div className="sop-kpi__progress"><span style={{ width: `${completionPct}%` }} /></div>
        </div>
      </div>

      {/* ── 8-stage stepper enriched with assignee avatars ── */}
      <div className="sop-stepper" role="list">
        {stages.map((s, i) => {
          const isCurrent = s.id === current.id;
          const isDone    = i < currentIdx;
          const isPending = i > currentIdx;
          const meta = stageMeta[s.id];
          const cls = ["sop-step"];
          if (isCurrent) cls.push("is-current");
          if (isDone)    cls.push("is-done");
          if (isPending) cls.push("is-pending");
          if (s.id === selectedStage && !isCurrent) cls.push("is-selected");
          return (
            <button key={s.id} className={cls.join(" ")} onClick={() => setSelectedStage(s.id)} role="listitem">
              <div className="sop-step__n">{isDone ? <Icon name="check" size={11} /> : s.order}</div>
              <div className="sop-step__name">{s.name}</div>
              <div className="sop-step__meta">{isCurrent ? "current" : isDone ? "complete" : "pending"}</div>
              <div className="sop-step__owner" title={`${meta.assignee} · ${meta.role}`}>
                <span className="sop-avatar sop-avatar--sm" style={{ background: meta.color, opacity: isPending ? 0.4 : 1 }}>{meta.avatar}</span>
                <span style={{ fontSize: 10.5, color: isPending ? "var(--fg2)" : "var(--fg1)", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{meta.assignee}</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* ── Main: Stage detail · Owner panel · Approvals ── */}
      <div className="sop-detail-grid">
        <div className="sop-check-card">
          <div className="sop-check-card__head">
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                <h3 style={{ margin: 0 }}>Stage {view.order} · {view.name}</h3>
                {viewIsCurrent ? <span className="chip chip--blue" style={{ fontSize: 10 }}>CURRENT</span> : null}
                {viewIsDone    ? <span className="chip chip--green" style={{ fontSize: 10 }}>COMPLETE</span> : null}
                {viewIsPending ? <span className="chip chip--ghost" style={{ fontSize: 10 }}>PENDING</span> : null}
              </div>
              <div className="sub">
                {viewIsCurrent ? "Acceptance checks gate advancement to the next stage. All must pass." :
                  viewIsDone ? "Stage closed. Acceptance checks were verified at transition time." :
                  "Stage pending. Will become active once the prior stage advances."}
              </div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn--ghost btn--sm" disabled={viewIdx === 0}
                onClick={() => setSelectedStage(stages[Math.max(0, viewIdx - 1)].id)}>
                <Icon name="chevron-left" /> Prev
              </button>
              <button className="btn btn--ghost btn--sm" disabled={viewIdx === stages.length - 1}
                onClick={() => setSelectedStage(stages[Math.min(stages.length - 1, viewIdx + 1)].id)}>
                Next <Icon name="chevron-right" />
              </button>
            </div>
          </div>

          {viewChecks.map((c, i) => (
            <div key={i} className={`sop-check is-${c.state}`}>
              <div className="sop-check__icon">
                {c.state === "pass" ? <Icon name="check" size={12} /> :
                 c.state === "fail" ? <Icon name="x" size={12} /> :
                 <Icon name="circle-dot" size={10} />}
              </div>
              <div>
                <div className="sop-check__name">{c.label}</div>
                <div className="sop-check__meta">
                  {c.meta}
                  {c.actor && c.actor !== "—" && c.state === "pass" ? <span> · by <strong style={{ color: "var(--fg1)" }}>{c.actor}</strong></span> : null}
                </div>
              </div>
              <div>
                {c.state === "fail"
                  ? <button className="btn btn--secondary btn--sm" data-test-id={`sop-resolve-${c.label.slice(0, 20)}`} onClick={() => wired.resolveCheck(c.label)}>Resolve</button>
                  : c.state === "pass"
                    ? <span className="chip chip--green"><Icon name="check" size={10} /> pass</span>
                    : <span className="chip chip--ghost"><span className="chip__dot" /> pending</span>}
              </div>
            </div>
          ))}

          {viewIsCurrent ? (
            <div className={`sop-advance-row ${canAdvance ? "is-ready" : "is-blocked"}`}>
              <div>
                <div style={{ fontWeight: 700, color: "var(--fg1)", fontSize: 13 }}>
                  {canAdvance ? "Ready to advance" : "Cannot advance"}
                </div>
                <div style={{ fontSize: 12, color: "var(--fg2)", marginTop: 2 }}>
                  {canAdvance ? `All ${checkStates.length} checks pass. Advance to ${next?.name || "—"}.` :
                    `${blockers} check(s) blocking advancement to ${next?.name || "—"}.`}
                </div>
              </div>
              <button className="btn btn--primary" disabled={!canAdvance} data-test-id="sop-advance" onClick={async () => {
                if (!next) return;
                const ok = await wired.advanceStage(session.title, current.name, next.name);
                if (ok) setSelectedStage(next.id);
              }}>
                <Icon name="chevron-right" size={12} /> Advance to {next?.name || "—"}
              </button>
            </div>
          ) : null}
        </div>

        {/* Side rail: stage owner + approvals + actions */}
        <div className="sop-side">
          <div className="card sop-owner-card">
            <div className="card__header"><h3>Stage owner</h3></div>
            <div className="card__body">
              <div className="sop-owner">
                <span className="sop-avatar sop-avatar--lg" style={{ background: viewMeta?.color }}>{viewMeta?.avatar}</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14, color: "var(--fg1)" }}>{viewMeta?.assignee}</div>
                  <div style={{ fontSize: 12, color: "var(--fg2)", marginTop: 2 }}>{viewMeta?.role}</div>
                </div>
              </div>
              <div className="sop-owner-actions">
                <button className="btn btn--secondary btn--sm" onClick={() => wired.reassignStage(view.name)}><Icon name="edit" /> Reassign</button>
                <button className="btn btn--ghost btn--sm" onClick={() => wired.toastInfo(`Pinged ${viewMeta?.assignee} on Slack (mock)`)}><Icon name="message" /> Ping</button>
              </div>
              <div className="sop-owner-meta">
                <div><span className="sop-lbl">Notify on entry</span><span style={{ color: "var(--color-green)", fontWeight: 700 }}>ON</span></div>
                <div><span className="sop-lbl">SLA target</span><span>2 days</span></div>
                <div><span className="sop-lbl">Status</span><span>{viewIsCurrent ? "Awaiting attestation" : viewIsDone ? "Signed off" : "Queued"}</span></div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card__header"><h3>Approvals</h3><span className="chip chip--ghost" style={{ fontSize: 10 }}>{approvers.length} of {stages.length - 1}</span></div>
            <div className="card__body" style={{ padding: 0 }}>
              {approvers.length === 0 ? (
                <div style={{ padding: 16, fontSize: 12, color: "var(--fg2)", textAlign: "center" }}>No approvals yet.</div>
              ) : approvers.map((a, i) => (
                <div key={i} className="sop-approval">
                  <span className="sop-avatar sop-avatar--sm" style={{ background: a.color }}>{a.avatar}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--fg1)" }}>{a.by}</div>
                    <div style={{ fontSize: 10.5, color: "var(--fg2)" }}>{a.stage.name} · {new Date(a.at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: false })}</div>
                  </div>
                  <Icon name="check" size={14} className="sop-approval__check" />
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card__header"><h3>Quick actions</h3></div>
            <div className="card__body" style={{ display: "grid", gap: 6 }}>
              <Link to={`/e/${session.id}`} className="btn btn--secondary btn--sm"><Icon name="edit" /> Open editor</Link>
              <Link to={`/e/${session.id}/audit`} className="btn btn--secondary btn--sm"><Icon name="history" /> Full audit ledger</Link>
              <button className="btn btn--ghost btn--sm" onClick={() => wired.toastInfo("Override modal (mock)")}><Icon name="alert" /> Override with reason</button>
              <button className="btn btn--ghost btn--sm" onClick={() => wired.toastInfo("Stage notes (mock)")}><Icon name="doc" /> Stage notes</button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Transition history + Invariants ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 18 }}>
        <div className="card">
          <div className="card__header"><h3>Stage Transition History</h3><span className="chip chip--ghost" style={{ fontSize: 10 }}>{transitions.length} transitions</span></div>
          <div className="card__body" style={{ padding: 0 }}>
            {transitions.map((t, i) => (
              <div key={i} className="sop-transition">
                <span className="sop-transition__t">
                  {new Date(t.at).toISOString().slice(0, 16).replace("T", " ")}
                </span>
                <div className="sop-transition__main">
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <StageBadge id={t.from} />
                    <Icon name="chevron-right" size={12} />
                    <StageBadge id={t.to} />
                  </div>
                  <div style={{ fontSize: 12, color: "var(--fg2)", marginTop: 4 }}>{t.note}</div>
                </div>
                <div className="sop-transition__actor">
                  <span className="sop-avatar sop-avatar--sm" style={{ background: t.actorColor }}>{t.actorAvatar}</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--fg1)" }}>{t.actor}</div>
                    <div style={{ fontSize: 10, color: "var(--fg2)" }}>{t.actorRole}</div>
                  </div>
                </div>
              </div>
            ))}
            <div style={{ padding: "12px 16px", color: "var(--fg2)", fontSize: 12, fontStyle: "italic" }}>
              — current state (<strong>{current.name}</strong>) since {currentSinceDate.toISOString().slice(0, 16).replace("T", " ")} ·  assigned to <strong>{stageMeta[current.id]?.assignee}</strong> —
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card__header"><h3>SOP Invariants</h3></div>
          <div className="card__body" style={{ fontSize: 12, color: "var(--fg2)", lineHeight: 1.65 }}>
            <div className="sop-invariant">
              <span className="chip chip--green"><Icon name="check" size={10} /> L5</span>
              <span><strong style={{ color: "var(--fg1)" }}>No stage skipping.</strong> Transitions are deterministic and replayable. Verified by workflow replay harness.</span>
            </div>
            <div className="sop-invariant">
              <span className="chip chip--green"><Icon name="check" size={10} /> §18.14</span>
              <span><strong style={{ color: "var(--fg1)" }}>Append-only audit trail.</strong> Each transition writes a row; the row is never mutated.</span>
            </div>
            <div className="sop-invariant">
              <span className="chip chip--green"><Icon name="check" size={10} /> §15.6</span>
              <span><strong style={{ color: "var(--fg1)" }}>8-stage parity.</strong> Stages, gates, and acceptance checks ported byte-for-byte from v3.12.</span>
            </div>
            <div className="sop-invariant">
              <span className="chip chip--blue"><Icon name="circle-dot" size={10} /> ADR</span>
              <span><strong style={{ color: "var(--fg1)" }}>Per-stage override.</strong> Override with reason is queued in <Link to="/improvements">Improvement Request i5</Link>.</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

window.SopRoute = SopRoute;
