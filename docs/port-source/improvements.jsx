/* eslint-disable no-undef */
// Improvements route — /improvements
// Master/detail: list left, action-plan wizard right.

function ImprovementsRoute() {
  const [extraItems, setExtraItems] = useState([]);
  const items = [...extraItems, ...MIC_DATA.IMPROVEMENTS];
  const [statusTab, setStatusTab] = useState("all");
  const [selectedId, setSelectedId] = useState(items[1]?.id || items[0]?.id);
  const [wizardStep, setWizardStep] = useState(0);
  const [searchQ, setSearchQ] = useState("");

  const filters = [
    { id: "all",            label: "All",          count: items.length },
    { id: "pending",        label: "Pending",      count: items.filter((i) => i.status === "pending").length },
    { id: "under-review",   label: "Under Review", count: 0 },
    { id: "approved",       label: "Approved",     count: 0 },
    { id: "in-progress",    label: "In Progress",  count: 0 },
    { id: "rolled-out",     label: "Rolled Out",   count: items.filter((i) => i.status === "rolled-out").length },
    { id: "declined",       label: "Declined",     count: 0 },
    { id: "archived",       label: "Archived",     count: 0 },
  ];

  const visibleItems = (statusTab === "all" ? items : items.filter((i) => i.status === statusTab))
    .filter((i) => !searchQ || (i.title || "").toLowerCase().includes(searchQ.toLowerCase()));
  const selected = items.find((i) => i.id === selectedId) || items[0];

  const wizardSteps = [
    { id: 0, label: "Overview",       sub: "Summary & plan" },
    { id: 1, label: "Requirements",   sub: "Acceptance criteria" },
    { id: 2, label: "Implementation", sub: "Dev prompt" },
    { id: 3, label: "Testing",        sub: "Validation plan" },
    { id: 4, label: "Review",         sub: "Approve & save" },
  ];

  const plan = [
    "Requirements Clarification",
    "Implementation Scope",
    "Testing & Validation",
    "Rollout & Documentation",
  ];

  const history = [
    { from: "pending",     to: "approved",    by: "johndean@vin.com",  at: "May 6, 08:09 AM" },
    { from: "approved",    to: "in_progress", by: "johndean@vin.com",  at: "May 6, 08:17 AM" },
    { from: "in_progress", to: "rolled_out",  by: "johndean@vin.com",  at: "May 6, 07:22 PM" },
  ];

  return (
    <main className="page" data-screen-label="Improvements">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div>
          <h1 className="page-title">Improvements</h1>
          <p className="page-desc">
            {items.length} of {items.length} · roadmap for product enhancements, bug fixes, and operator requests.
          </p>
        </div>
        <div className="page-actions">
          <div className="search" style={{ flex: "0 0 240px" }}>
            <Icon name="search" />
            <input placeholder="Search…" value={searchQ} onChange={(e) => setSearchQ(e.target.value)} data-test-id="improv-search" />
          </div>
          <button className="btn btn--primary" data-test-id="improv-suggest" onClick={() => wired.openSuggestImprovement((newItem) => setExtraItems((prev) => [{ ...newItem, status: "pending", risk: "low", area: "UX/UI", created: new Date().toISOString(), author: "kschultz@vin.com", url: "" }, ...prev]))}>
            <Icon name="circle-dot" /> Suggest Improvement
          </button>
        </div>
      </div>

      {/* Status tabs */}
      <div className="improv-tabs">
        {filters.map((f) => (
          <button key={f.id} className={`improv-tab ${statusTab === f.id ? "is-active" : ""}`} onClick={() => setStatusTab(f.id)}>
            {f.label} <span className="count">{f.count}</span>
          </button>
        ))}
      </div>

      {/* Master/detail */}
      <div className="improv-master-detail">
        <div className="improv-master">
          <div className="improv-master__head">
            <input type="checkbox" />
            <span>TITLE</span>
            <span>STATUS</span>
            <span>RISK</span>
            <span>PRIORITY</span>
            <span>SUBMITTED</span>
          </div>
          <div className="improv-master__list">
            {visibleItems.map((it) => {
              const isSel = it.id === selectedId;
              return (
                <div key={it.id} className={`improv-row2 ${isSel ? "is-selected" : ""}`} onClick={() => setSelectedId(it.id)}>
                  <input type="checkbox" onClick={(e) => e.stopPropagation()} />
                  <div>
                    <div className="improv-row2__title">{it.title}</div>
                    <div className="improv-row2__url">{it.url}</div>
                  </div>
                  <div>
                    {it.status === "pending"     && <span className="status-pill status-pill--pending">PENDING</span>}
                    {it.status === "rolled-out"  && <span className="status-pill status-pill--rolled">ROLLED OUT</span>}
                  </div>
                  <div>
                    {it.risk === "critical" && <span className="risk-pill risk-pill--critical">CRITICAL</span>}
                    {it.risk === "high"     && <span className="risk-pill risk-pill--high">HIGH</span>}
                    {it.risk === "medium"   && <span className="risk-pill risk-pill--medium">MEDIUM</span>}
                    {it.risk === "low"      && <span className="risk-pill risk-pill--low">LOW</span>}
                  </div>
                  <div className="improv-row2__priority">
                    {it.priority === "crit" ? "Critical" : it.priority === "high" ? "High" : it.priority === "med" ? "Medium" : "Low"}
                  </div>
                  <div className="improv-row2__date">
                    {new Date(it.created).toLocaleDateString("en-US", { month: "short", day: "numeric" })}, {new Date(it.created).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })}
                  </div>
                  <span className="improv-row2__del" data-test-id={`improv-del-${it.id}`} onClick={async (e) => { e.stopPropagation(); const ok = await confirm.open({ title: "Delete improvement?", body: `"${it.title}"`, danger: true, confirmLabel: "Delete" }); if (ok) { setExtraItems((prev) => prev.filter((x) => x.id !== it.id)); auditLog.log("You", "delete", `Deleted ${it.id}`); toast.push("Improvement deleted", { tone: "ok" }); } }}>Del</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Detail pane */}
        <div className="improv-detail">
          <ImprovDetail item={selected} onClose={() => setSelectedId(null)} />
        </div>
      </div>
    </main>
  );
}

// ── Improvement detail — 5-step Action Plan Builder ────────
function ImprovDetail({ item, onClose }) {
  const [step, setStep] = useState(0);
  const [model, setModel] = useState("Gemini 2.5 Pro (recommended)");
  const [adminStatus, setAdminStatus] = useState(item.status === "rolled-out" ? "Rolled out" : "Approved");
  const [adminRisk, setAdminRisk] = useState((item.risk || "low").toUpperCase());
  const [adminVersion, setAdminVersion] = useState("");
  const [adminNotes, setAdminNotes] = useState(
    `AI Transcript Karaoke + Click-to-Seek — Phase 2-Mega Plan v2 (post-adversarial-review)\n\n> **Scope.** Make AI Transcript pane karaoke + click-to-seek work end-to-end during playback. Frontend-only. No migrations.`
  );
  const [expandAll, setExpandAll] = useState(false);
  const [openSections, setOpenSections] = useState({ requirements: true, implementation: false, testing: false });

  const steps = [
    { id: 0, label: "Overview",       sub: "Summary" },
    { id: 1, label: "Requirements",   sub: "Criteria" },
    { id: 2, label: "Implementation", sub: "Dev prompt" },
    { id: 3, label: "Testing",        sub: "Validation" },
    { id: 4, label: "Review",         sub: "Approve" },
  ];

  const riskUp = (item.risk || "low").toUpperCase();
  const impId = item.id.startsWith("IMP-") ? item.id : `IMP-${String(parseInt(item.id.replace(/\D/g, ""), 10) + 999).padStart(4, "0")}`;
  const typeLabel = (item.area || "Bug Fix");

  const reqDoc = `## Requirements: ${item.title}

### Objective
${typeLabel} · ${item.description ? item.description.slice(0, 80) : `reported at ${item.surface || "/admin/improvements/"}`}

### Scope
- **Affected Area:** ${item.surface || "General"}
- **Risk Classification:** ${riskUp}
- **Improvement Type:** ${typeLabel}
- **Priority:** ${item.priority === "crit" ? "Critical" : item.priority === "high" ? "High" : item.priority === "med" ? "Medium" : "Low"}
- **Impact Scope:** Single Page
- **Plan Steps:** 5

### Acceptance Criteria
- [ ] **Step 1 — Root Cause Analysis:** Investigate and identify the root cause of the reported bug. Document reproduction steps and affected components.
- [ ] **Step 2 — Implementation Scope:** Define the technical implementation plan, affected components, and estimated effort.
- [ ] **Step 3 — Fix Verification:** Verify the fix resolves the original issue without introducing regressions. Confirm reproduction steps no longer trigger the bug.
- [ ] **Step 4 — Testing & Validation:** Create test cases covering happy paths, edge cases, and regression scenarios.
- [ ] **Step 5 — Rollout & Documentation:** Plan staged rollout, update Help Center articles, and notify affected users.`;

  const implDoc = `## Implementation Prompt: ${item.title}

### Context
${typeLabel} · ${item.description ? item.description.slice(0, 80) : `reported at ${item.surface || "/admin/improvements/"}`}

**Affected Area:** ${item.surface || "General"}
**Risk Level:** ${riskUp}
**Type:** ${typeLabel}
**Impact Scope:** Single Page

### Requirements Summary
- [ ] **Step 1 — Root Cause Analysis:** Investigate and identify the root cause of the reported bug. Document reproduction steps and affected components.
- [ ] **Step 2 — Implementation Scope:** Define the technical implementation plan, affected components, and estimated effort.
- [ ] **Step 3 — Fix Verification:** Verify the fix resolves the original issue without introducing regressions. Confirm reproduction steps no longer trigger the bug.
- [ ] **Step 4 — Testing & Validation:** Create test cases covering happy paths, edge cases, and regression scenarios.
- [ ] **Step 5 — Rollout & Documentation:** Plan staged rollout, update Help Center articles, and notify affected users.

### Affected Components
- \`To be determined based on scope analysis\``;

  const testDoc = `## Test Plan: ${item.title}

### Test Objectives
Validate that the implementation of "${item.title}" meets all acceptance criteria, handles edge cases gracefully, and does not introduce regressions.

### Happy Path Scenarios
**Scenario 1: Root Cause Analysis**
- Given: The system is in its current production state
- When: Investigate and identify the root cause of the reported bug. Document reproduction steps and affected components.
- Then: The step completes successfully without errors

**Scenario 2: Implementation Scope**
- Given: The system is in its current production state
- When: Define the technical implementation plan, affected components, and estimated effort.
- Then: The step completes successfully without errors

**Scenario 3: Fix Verification**
- Given: The system is in its current production state
- When: Verify the fix resolves the original issue without introducing regressions.
- Then: The step completes successfully without errors

**Scenario 4: Testing & Validation**`;

  const docOf = (k) => k === "requirements" ? reqDoc : k === "implementation" ? implDoc : testDoc;
  const linesOf = (txt) => txt.split("\n").length;
  const copyText = async (text, label) => {
    try { await navigator.clipboard.writeText(text); toast.push(`${label} copied`, { tone: "ok" }); }
    catch { toast.push("Clipboard blocked", { tone: "attn" }); }
  };
  const exportMd = () => {
    const merged = `# ${item.title}\n\n${reqDoc}\n\n---\n\n${implDoc}\n\n---\n\n${testDoc}\n`;
    downloadBlob(merged, `${impId}.md`, "text/markdown");
    toast.push(".md exported", { tone: "ok" });
  };
  const overviewBody = () => (
    <div className="impv-overview">
      <div className="impv-grid-2">
        <div><div className="impv-lbl">Submitted by</div><div className="impv-val">{item.author}</div></div>
        <div><div className="impv-lbl">Area</div><div className="impv-val">{item.surface || item.area}</div></div>
        <div><div className="impv-lbl">Created</div><div className="impv-val">{new Date(item.created).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: true })}</div></div>
        <div><div className="impv-lbl">Current Status</div><div className="impv-val">
          {item.status === "rolled-out" ? <span className="status-pill status-pill--rolled" style={{ display: "block", textAlign: "center", padding: "5px 0" }}>ROLLED OUT</span> : null}
          {item.status === "pending"    ? <span className="status-pill status-pill--pending" style={{ display: "block", textAlign: "center", padding: "5px 0" }}>PENDING</span> : null}
        </div></div>
        <div><div className="impv-lbl">Type</div><div className="impv-val">{typeLabel}</div></div>
        <div><div className="impv-lbl">Priority</div><div className="impv-val">{item.priority === "crit" ? "Critical" : item.priority === "high" ? "High" : item.priority === "med" ? "Medium" : "Low"}</div></div>
        <div><div className="impv-lbl">Impact Scope</div><div className="impv-val">Single Page</div></div>
        <div><div className="impv-lbl">Affected Roles</div><div className="impv-val" style={{ color: "var(--fg2)" }}>—</div></div>
      </div>
      <div className="impv-section">
        <div className="impv-lbl">Description</div>
        <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--fg1)", lineHeight: 1.6 }}>{item.description}</p>
      </div>
    </div>
  );

  const promptBlock = (title, doc, kind) => (
    <>
      <div className="impv-prompt-head">
        <span className="impv-prompt-eyebrow">{title}</span>
        <button className="btn btn--secondary btn--sm" onClick={() => { toast.push("Regenerating…"); setTimeout(() => toast.push("Regenerated", { tone: "ok" }), 600); }}><Icon name="history" size={11} /> Regenerate</button>
      </div>
      <pre className="impv-mdcode">{doc}</pre>
    </>
  );

  return (
    <>
      <div className="impv-head">
        <div>
          <h2 className="impv-title">{item.title}</h2>
          <p className="impv-sub">Action Plan Builder · {impId}</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className={`risk-pill risk-pill--${item.risk || "low"}`}>{riskUp}</span>
          <button className="btn btn--ghost btn--icon btn--sm" title="Close" onClick={onClose}><Icon name="x" size={12} /></button>
        </div>
      </div>

      <div className="impv-stepper">
        {steps.map((s) => {
          const done = step > s.id;
          const active = step === s.id;
          return (
            <button key={s.id} className={`impv-step ${active ? "is-active" : ""} ${done ? "is-done" : ""}`} onClick={() => setStep(s.id)}>
              <span className="impv-step__circle">{done ? <Icon name="check" size={12} /> : s.id + 1}</span>
              <div className="impv-step__label">{s.label}</div>
              <div className="impv-step__sub">{s.sub}</div>
            </button>
          );
        })}
      </div>

      <div className="impv-modelbar">
        <span className="impv-modelbar__lbl">AI Model:</span>
        <select className="impv-modelbar__select" value={model} onChange={(e) => setModel(e.target.value)}>
          <option>Gemini 2.5 Pro (recommended)</option>
          <option>Gemini 2.5 Flash</option>
          <option>GPT-5</option>
          <option>Claude Opus 4.5</option>
        </select>
        <Icon name="chevron-right" size={12} className="impv-modelbar__chev" />
      </div>

      <div className="impv-body">
        {step === 0 ? overviewBody() : null}
        {step === 1 ? promptBlock("REQUIREMENTS DOCUMENT", reqDoc, "requirements") : null}
        {step === 2 ? promptBlock("IMPLEMENTATION PROMPT", implDoc, "implementation") : null}
        {step === 3 ? promptBlock("TESTING & VALIDATION PROMPT", testDoc, "testing") : null}

        {step === 4 ? (
          <div className="impv-review">
            <div className="impv-review__toolbar">
              <button className="btn btn--secondary btn--sm" onClick={() => { setExpandAll(true); setOpenSections({ requirements: true, implementation: true, testing: true }); }}>+ Expand All</button>
              <span style={{ marginLeft: "auto", display: "inline-flex", gap: 6 }}>
                <button className="btn btn--ghost btn--sm" onClick={() => copyText(`${reqDoc}\n\n${implDoc}\n\n${testDoc}`, "Action plan")}><Icon name="doc" size={11} /> Copy to Clipboard</button>
                <button className="btn btn--ghost btn--sm" onClick={exportMd}><Icon name="download" size={11} /> Export (.md)</button>
              </span>
            </div>
            {[
              { k: "requirements",   label: "REQUIREMENTS",        doc: reqDoc },
              { k: "implementation", label: "IMPLEMENTATION PROMPT", doc: implDoc },
              { k: "testing",        label: "TESTING & VALIDATION", doc: testDoc },
            ].map((s) => {
              const open = expandAll || openSections[s.k];
              return (
                <div key={s.k} className={`impv-accord ${open ? "is-open" : ""}`}>
                  <div className="impv-accord__head" onClick={() => setOpenSections((p) => ({ ...p, [s.k]: !p[s.k] }))}>
                    <Icon name={open ? "chevron-down" : "chevron-right"} size={12} />
                    <span className="impv-accord__title">{s.label}</span>
                    <span className="impv-accord__meta">{linesOf(s.doc)} lines · generated 2m ago</span>
                    <button className="btn btn--ghost btn--sm" onClick={(e) => { e.stopPropagation(); copyText(s.doc, s.label); }}><Icon name="doc" size={11} /> Copy</button>
                  </div>
                  {open ? <pre className="impv-mdcode impv-mdcode--inset">{s.doc}</pre> : null}
                </div>
              );
            })}

            <div className="impv-admin">
              <div className="impv-admin__head">ADMIN CONTROLS</div>
              <div className="impv-admin__grid">
                <label>
                  <span className="impv-lbl">Status</span>
                  <select value={adminStatus} onChange={(e) => setAdminStatus(e.target.value)} className="impv-input">
                    <option>Pending</option><option>Under Review</option><option>Approved</option><option>In Progress</option><option>Rolled out</option><option>Declined</option>
                  </select>
                </label>
                <label>
                  <span className="impv-lbl">Risk Level</span>
                  <select value={adminRisk} onChange={(e) => setAdminRisk(e.target.value)} className="impv-input">
                    <option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option>
                  </select>
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  <span className="impv-lbl">Target Version</span>
                  <input value={adminVersion} onChange={(e) => setAdminVersion(e.target.value)} placeholder="e.g. 3.12" className="impv-input" />
                </label>
                <label style={{ gridColumn: "1 / -1" }}>
                  <span className="impv-lbl">Admin Notes</span>
                  <textarea value={adminNotes} onChange={(e) => setAdminNotes(e.target.value)} rows={4} className="impv-input" style={{ fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.55, resize: "vertical" }} />
                </label>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="impv-nav">
        <button className="btn btn--secondary" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>‹ Back</button>
        {step < 4 ? (
          <button className="btn btn--primary" style={{ background: "var(--color-green)" }} onClick={() => setStep(step + 1)}>Next ›</button>
        ) : (
          <button className="btn btn--primary" style={{ background: "var(--color-green)" }} onClick={() => { auditLog.log("You", "improvement_save", `Saved ${impId} — status ${adminStatus}, risk ${adminRisk}`); toast.push("Changes saved", { tone: "ok" }); }}>Save Changes</button>
        )}
      </div>
    </>
  );
}
function _LEGACY_SETTINGS_MARKER() { return null; }
// ── Settings — multi-section ────────────────────────────────
function SettingsRoute() {
  const sections = [
    { id: "general",     label: "General" },
    { id: "team",        label: "Team & roles" },
    { id: "types",       label: "Types & stage defaults" },
    { id: "ai-models",   label: "AI models" },
    { id: "upload",      label: "Upload & storage" },
    { id: "discrepancy", label: "Discrepancy classification" },
    { id: "export",      label: "Export" },
    { id: "prompts",     label: "Prompt templates" },
    { id: "manifest",    label: "Session manifest" },
    { id: "email",       label: "Email" },
    { id: "diagnostics", label: "Diagnostics" },
    { id: "deleted",     label: "Deleted sessions" },
  ];
  const [active, setActive] = useState("general");

  return (
    <main className="settings-page" data-screen-label="Settings">
      <aside className="settings-nav" aria-label="Settings sections">
        <h2 className="page-title" style={{ fontSize: 22, marginBottom: 18 }}>Settings</h2>
        <ul>
          {sections.map((s) => (
            <li key={s.id}>
              <button className={`settings-nav__item ${active === s.id ? "is-active" : ""}`} onClick={() => setActive(s.id)}>{s.label}</button>
            </li>
          ))}
        </ul>
      </aside>
      <section className="settings-content">
        <SettingsRouterPane active={active} />
      </section>
    </main>
  );
}

// Renders a settings section using the same layout as the Email page.
function SettingsSection({ config }) {
  return (
    <>
      <div className="settings-row">
        <div>
          <h3>{config.title}</h3>
          <p>{config.lead}</p>
        </div>
        {config.headerCta ? <button className="btn btn--tertiary" data-test-id={`settings-headerCta-${config.title.replace(/\s/g, "_")}`} onClick={wired.saveSetting(config.title)}>{config.headerCta}</button> : null}
      </div>
      {config.cards.map((c, i) => (
        <div key={i} className="settings-card">
          <div className="settings-card__row">
            <div>
              <div className="settings-eyebrow">{c.eyebrow}</div>
              <h4 style={{ margin: "6px 0 6px", fontSize: 16, fontWeight: 700, color: "var(--fg1)" }}>{c.heading}</h4>
              <p style={{ margin: 0, fontSize: 13, color: "var(--fg2)", lineHeight: 1.6 }}
                 dangerouslySetInnerHTML={{ __html: c.body }} />
            </div>
            {c.cta ? <button className="btn btn--tertiary" data-test-id={`settings-cta-${(c.heading || c.eyebrow).replace(/\s/g, "_").slice(0, 30)}`} onClick={() => { if (c.cta && c.cta.toLowerCase().includes("test")) wired.testEmail(); else wired.saveSetting(c.heading || c.eyebrow)(); }}>{c.cta}</button> : null}
          </div>
        </div>
      ))}
    </>
  );
}

// Per-section content. Each section uses the same "lead + 2 cards" scaffold
// as Email so navigation between sections preserves visual position.
const SETTINGS_CONFIG = {
  general: {
    title: "General",
    lead: "Workspace identity, default locale, and time zone.",
    headerCta: "Edit organisation",
    cards: [
      { eyebrow: "WORKSPACE · IDENTITY", heading: "Organisation name & brand",
        body: "Display name shown across the editor, exports, and notification templates. Logo is uploaded once and re-used everywhere.", cta: "Open editor" },
      { eyebrow: "LOCALE · TIME ZONE",  heading: "Default locale & time zone",
        body: "Defaults: <strong>en-US</strong> · <strong>America/Chicago (CT)</strong>. Used for timestamps, SRT generation, and operator-visible dates.", cta: "Open preferences" },
    ],
  },
  team: {
    title: "Team & roles",
    lead: "Members, role assignments, and per-stage permissions.",
    headerCta: "Invite member",
    cards: [
      { eyebrow: "MEMBERS · 18 ACTIVE", heading: "Active members",
        body: "Manage operator access. Roles: <strong>admin · reviewer · copy editor · medical reviewer · viewer</strong>. Removing a member preserves their audit-ledger entries (append-only).", cta: "Open members" },
      { eyebrow: "ROLES · PERMISSIONS", heading: "Per-stage permissions",
        body: "Which roles can advance each SOP stage. Defaults: <strong>medical reviewer</strong> advances Medical Review; <strong>copy editor</strong> advances Copy edit (draft) and (final). Override per-Type in the matrix below.", cta: "Open matrix" },
    ],
  },
  types: {
    title: "Types & stage defaults",
    lead: "Per-Type × per-Stage defaults: assignee, notify-on-entry, acceptance check overrides.",
    headerCta: "Open Types matrix",
    cards: [
      { eyebrow: "TYPES · 4 DEFINED",   heading: "Session types",
        body: "<strong>Lecture · Rounds · Q&amp;A · Interview</strong>. Each Type carries its own stage defaults — assignee, notify-on-entry, and prompt template overrides.", cta: "Manage types" },
      { eyebrow: "STAGE DEFAULTS · MATRIX", heading: "Stage assignee defaults",
        body: "Each Type × Stage cell holds: <em>assignee</em> (person or group), <em>Email</em> toggle, <em>prompt override</em>. The matrix is the source of truth for new sessions.", cta: "Open Types matrix" },
    ],
  },
  "ai-models": {
    title: "AI models",
    lead: "Model selection, fallback chain, and rate-limit policy.",
    headerCta: "Edit model rules",
    cards: [
      { eyebrow: "PRIMARY · GEMINI 2.5 PRO", heading: "Primary model",
        body: "Default model for all AI Processing Modes. Fallback chain: <code>Gemini 2.5 Pro → Gemini 2.5 Flash → GPT-5</code>. Failure threshold: 2 consecutive timeouts.", cta: "Open primary" },
      { eyebrow: "QUOTA · RATE LIMIT",  heading: "Quota & retry policy",
        body: "Tokens per minute: <strong>2.4M</strong>. Retry: <strong>exponential backoff, capped at 12 attempts</strong>. Per §15.5 discrepancy classification poll cap.", cta: "Open quota" },
    ],
  },
  upload: {
    title: "Upload & storage",
    lead: "Bucket configuration, retention policy, and the extras2 manifest contract.",
    headerCta: "Open storage",
    cards: [
      { eyebrow: "GCS · BUCKET",        heading: "Asset bucket",
        body: "Primary: <code>gs://vin-transcripts</code> · region <strong>us-central1</strong>. Uniform ACLs · CMEK rotation < 90d · audit log streaming on.", cta: "Open bucket" },
      { eyebrow: "RETENTION · POLICY",  heading: "Retention & lifecycle",
        body: "Source media retained <strong>2 years</strong> · archived to Nearline after <strong>90 days</strong>. Append-only correction ledger has no deletion lifecycle.", cta: "Open policy" },
    ],
  },
  discrepancy: {
    title: "Discrepancy classification",
    lead: "Server-side LCS thresholds and per-class meaningfulness rules.",
    headerCta: "Edit thresholds",
    cards: [
      { eyebrow: "CLASSES · 4 KINDS",   heading: "Classification kinds",
        body: "<strong>drift · punctuation · filler · low_confidence</strong>. Only <em>drift</em> and <em>low_confidence</em> are meaningful by default — punctuation and filler never flag for review.", cta: "Open classes" },
      { eyebrow: "THRESHOLDS · TUNING", heading: "Per-class thresholds",
        body: "Drift edit-distance ≥ <strong>3</strong> · Low-confidence STT confidence < <strong>0.62</strong> · Filler matches against the IIL Tier 1/2/3 wordlists. Per §18.13 normalization contract.", cta: "Open thresholds" },
    ],
  },
  export: {
    title: "Export",
    lead: "Per-format export templates and post-export hooks.",
    headerCta: "Open export builder",
    cards: [
      { eyebrow: "FORMATS · 4 TARGETS", heading: "Export formats",
        body: "<strong>.docx</strong> (Word, macro-compatible) · <strong>.srt</strong> (captions) · <strong>.txt</strong> (plain) · <strong>.zip</strong> (Word macro bundle). Each carries its own template.", cta: "Open formats" },
      { eyebrow: "HOOKS · POST-EXPORT", heading: "Webhooks & destinations",
        body: "On export complete: notify CMS, push to Wistia, write to VIN library. <strong>Paired <code>URL.revokeObjectURL</code></strong> guaranteed on every export (no blob URL leaks).", cta: "Open hooks" },
    ],
  },
  prompts: {
    title: "Prompt templates",
    lead: "Saved prompts used by AI Processing Modes and Custom Prompt sessions.",
    headerCta: "New template",
    cards: [
      { eyebrow: "AI PROMPT · DEFAULTS", heading: "Built-in prompts",
        body: "Each AI Processing Mode (Transcript / Summary / Key Moments / Structured Notes) has a built-in prompt that cannot be deleted. Edit to override per-workspace.", cta: "Open built-ins" },
      { eyebrow: "CUSTOM · USER",       heading: "Custom prompts",
        body: "User-defined prompts surface in the Upload page's <em>Load Saved Prompt Template</em> dropdown under the <strong>Custom</strong> optgroup. Includes <strong>Transcript (Paragraph v1)</strong> and 4 others.", cta: "Open custom" },
    ],
  },
  manifest: {
    title: "Session manifest",
    lead: "The extras2 manifest format that populates speaker labels, per-slide resources, and publishing links.",
    headerCta: "Open schema",
    cards: [
      { eyebrow: "SCHEMA · EXTRAS2",    heading: "Manifest schema",
        body: "Plaintext key-value blocks. Supported keys: <code>speakers</code> · <code>slide_resources</code> · <code>publishing_links</code> · <code>chat_anchors</code> · <code>poll_anchors</code>. The poll_anchors block is what auto-places polls inline.", cta: "Open schema" },
      { eyebrow: "VALIDATION · POLICY", heading: "Validation rules",
        body: "Manifest is parsed at upload time. Validation failures surface in the Processing trace (hop 3). Missing speaker bios warn but don't block (Speaker bios may still be missing).", cta: "Open rules" },
    ],
  },
  email: {
    title: "Email templates",
    lead: "Per-Type × per-Stage stage-notification HTML templates. Edit in the dedicated builder.",
    headerCta: "Open builder",
    cards: [
      { eyebrow: "STAGE ASSIGNEES + NOTIFY-ON-ENTRY CHECKBOXES", heading: "Stage triggers via Types matrix",
        body: "Stage-level email triggers live in the <strong>Types &amp; stage defaults</strong> matrix per Type. Each stage has a default assignee (person or group) and an optional <em>Email</em> toggle that fires the stage-notification template on entry.", cta: "Open Types matrix" },
      { eyebrow: "ADMIN · TEST EMAIL", heading: "Email send diagnostics",
        body: "Check SMTP config, test connectivity, and send a test email. Copyable diagnostic bundle for support tickets.", cta: "Open test page" },
    ],
  },
  diagnostics: {
    title: "Diagnostics",
    lead: "System health, observability counters, and operational probes.",
    headerCta: "Open dashboards",
    cards: [
      { eyebrow: "TELEMETRY · §20 OBSERVABILITY", heading: "Phase 0 counters",
        body: "Live values: <code>longtasks/min: 1</code> · <code>heap: 108 MB · flat over 30m</code> · <code>WS RTT: 18ms</code> · <code>autosave: 2s ago</code>. All seven §20 modules operational.", cta: "Open counters" },
      { eyebrow: "GCS · PIPELINE QA",   heading: "G1–G14 pipeline checks",
        body: "14 GCS-side checks running on a 5-minute cadence. 7-day uptime <strong>99.98%</strong>. Failing G13 (PII redaction sentinel) auto-rotating salt.", cta: "Open GCS QA" },
    ],
  },
  deleted: {
    title: "Deleted sessions",
    lead: "Soft-deleted sessions are recoverable for 30 days. After that, only the append-only ledger entries persist.",
    headerCta: "Open recovery",
    cards: [
      { eyebrow: "RECOVERY · 30-DAY WINDOW", heading: "Recoverable sessions",
        body: "Currently <strong>3</strong> sessions in the recovery window. Restore returns the session to its last-known SOP stage; the original audit ledger is replayed.", cta: "Open list" },
      { eyebrow: "PURGE · POLICY",      heading: "Beyond 30 days",
        body: "Source media is purged after 30 days. Correction ledger entries are <strong>preserved indefinitely</strong> per §18.11 (append-only invariant — no destructive deletion).", cta: "Open purge log" },
    ],
  },
};

function SuggestImprovementModal({ onSubmit }) {
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [type, setType] = useState("Enhancement");
  const [priority, setPriority] = useState("Low");
  const [area, setArea] = useState("");
  const [security, setSecurity] = useState(false);

  async function submit() {
    if (!title) { toast.push("Title required", { tone: "attn" }); return; }
    const r = await api.submitImprovement({ title, type, priority, area, security, desc });
    onSubmit && onSubmit({
      id: r.id,
      title,
      surface: area || "General",
      priority: priority.toLowerCase().slice(0, 4) === "crit" ? "crit" : priority.toLowerCase().slice(0, 3) === "hig" ? "high" : priority.toLowerCase().slice(0, 3) === "med" ? "med" : "low",
      area: type,
      description: desc,
    });
    auditLog.log("You", "improvement_submitted", `Filed ${r.id}: ${title}`);
    toast.push(`Submitted as ${r.id}`, { tone: "ok" });
    modal.close();
  }

  return (
    <div className="sugg-modal">
      <div className="sugg-modal__head">
        <h3 className="modal__title">Suggest improvement</h3>
        <button className="btn btn--ghost btn--icon btn--sm" onClick={modal.close}><Icon name="x" size={14} /></button>
      </div>
      <div className="sugg-modal__body">
        <label className="sugg-modal__field">
          <span>Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Brief title" autoFocus />
        </label>
        <label className="sugg-modal__field">
          <span>Description</span>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Describe the improvement…" rows={5} />
        </label>
        <div className="sugg-modal__row">
          <label className="sugg-modal__field">
            <span>Type</span>
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option>Enhancement</option><option>Bug Fix</option><option>Performance</option><option>UX/UI</option><option>Security</option><option>Workflow</option>
            </select>
          </label>
          <label className="sugg-modal__field">
            <span>Priority</span>
            <select value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option>Low</option><option>Medium</option><option>High</option><option>Critical</option>
            </select>
          </label>
        </div>
        <label className="sugg-modal__field">
          <span>Area</span>
          <input value={area} onChange={(e) => setArea(e.target.value)} placeholder="e.g. Editor, Pipeline, SOP" />
        </label>
        <label className="sugg-modal__check">
          <input type="checkbox" checked={security} onChange={(e) => setSecurity(e.target.checked)} />
          Security related
        </label>
      </div>
      <div className="sugg-modal__foot">
        <button className="btn btn--secondary" onClick={modal.close}>Cancel</button>
        <button className="btn sugg-modal__submit" onClick={submit}>Submit</button>
      </div>
    </div>
  );
}

// Override the wiring.jsx default modal with this richer one
window.SuggestImprovementModal = SuggestImprovementModal;
wired.openSuggestImprovement = (onSubmit) => modal.open(<SuggestImprovementModal onSubmit={onSubmit} />);
window.SettingsRoute = SettingsRoute;
