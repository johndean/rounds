/* eslint-disable no-undef */
// Wiring infrastructure — toast, confirm, mock api, audit-log store.
// All buttons / links across the app hook into these primitives so every
// click produces either a toast, a navigation, a state mutation, or a modal.

// ── Mock API ───────────────────────────────────────────────
const _delay = (ms = 320) => new Promise((r) => setTimeout(r, ms));
const _rand  = (n) => Math.floor(Math.random() * n);

const api = {
  async exportCSV()                   { await _delay(); return { ok: true }; },
  async deleteRow(id)                 { await _delay(); return { ok: true, id }; },
  async uploadFile(kind, name)        { await _delay(800); return { ok: true, kind, name }; },
  async download(kind, id)            { await _delay(); return { ok: true, kind, id, url: `blob:mock-${kind}-${id}` }; },
  async advanceStage(sid, from, to)   { await _delay(420); return { ok: true, sid, from, to }; },
  async editSegment(id, patch)        { await _delay(); return { ok: true, id, patch }; },
  async findReplace(q, r)             { await _delay(280); return { ok: true, count: _rand(8) + 1 }; },
  async submitImprovement(p)          { await _delay(); return { ok: true, id: "IMP-" + Date.now() }; },
  async saveSetting(label)            { await _delay(260); return { ok: true, label }; },
  async testEmail()                   { await _delay(420); return { ok: true }; },
  async sendNotification(stage, who)  { await _delay(); return { ok: true, stage, who }; },
  async cancelIngestion(sid)          { await _delay(); return { ok: true, sid }; },
  async resolveCheck(id)              { await _delay(); return { ok: true, id }; },
};

// ── Toast store ────────────────────────────────────────────
const _toasts = []; // {id, message, tone, action, ts}
const _toastListeners = new Set();
let _toastIdCounter = 0;
function _emitToasts() { _toastListeners.forEach((cb) => cb([..._toasts])); }
const toast = {
  push(message, opts = {}) {
    const id = ++_toastIdCounter;
    const item = { id, message, tone: opts.tone || "info", action: opts.action || null };
    _toasts.push(item);
    _emitToasts();
    const duration = opts.duration ?? 4000;
    if (duration > 0) setTimeout(() => toast.dismiss(id), duration);
    return id;
  },
  dismiss(id) {
    const idx = _toasts.findIndex((t) => t.id === id);
    if (idx >= 0) { _toasts.splice(idx, 1); _emitToasts(); }
  },
  subscribe(cb) { _toastListeners.add(cb); return () => _toastListeners.delete(cb); },
};

function useToasts() {
  const [items, setItems] = useState([..._toasts]);
  useEffect(() => toast.subscribe(setItems), []);
  return items;
}

function ToastHost() {
  const items = useToasts();
  return (
    <div className="toast-host" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={`toast toast--${t.tone}`}>
          <span className="toast__msg">{t.message}</span>
          {t.action ? (
            <button className="toast__action" onClick={() => { t.action.onClick(); toast.dismiss(t.id); }}>
              {t.action.label}
            </button>
          ) : null}
          <button className="toast__x" onClick={() => toast.dismiss(t.id)} aria-label="Dismiss">×</button>
        </div>
      ))}
    </div>
  );
}

// ── Confirm modal ──────────────────────────────────────────
let _confirmResolve = null;
const _confirmListeners = new Set();
let _confirmState = null;
function _setConfirm(state) {
  _confirmState = state;
  _confirmListeners.forEach((cb) => cb(state));
}
const confirm = {
  open(opts) {
    return new Promise((resolve) => {
      _confirmResolve = resolve;
      _setConfirm({ ...opts });
    });
  },
  accept() { if (_confirmResolve) _confirmResolve(true);  _confirmResolve = null; _setConfirm(null); },
  cancel() { if (_confirmResolve) _confirmResolve(false); _confirmResolve = null; _setConfirm(null); },
};

function ConfirmHost() {
  const [state, setState] = useState(_confirmState);
  useEffect(() => { _confirmListeners.add(setState); return () => _confirmListeners.delete(setState); }, []);
  if (!state) return null;
  return (
    <div className="modal-backdrop" onClick={confirm.cancel}>
      <div className="modal modal--confirm" onClick={(e) => e.stopPropagation()}>
        <h3 className="modal__title">{state.title || "Confirm"}</h3>
        {state.body ? <p className="modal__body">{state.body}</p> : null}
        <div className="modal__actions">
          <button className="btn btn--ghost" onClick={confirm.cancel}>{state.cancelLabel || "Cancel"}</button>
          <button className={`btn ${state.danger ? "btn--danger" : "btn--primary"}`} onClick={confirm.accept}>
            {state.confirmLabel || "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Generic modal (find/replace, segment edit, suggest improvement) ──
let _modalState = null;
const _modalListeners = new Set();
function _setModal(state) {
  _modalState = state;
  _modalListeners.forEach((cb) => cb(state));
}
const modal = {
  open(content)  { _setModal({ content }); },
  close()        { _setModal(null); },
};
function ModalHost() {
  const [state, setState] = useState(_modalState);
  useEffect(() => { _modalListeners.add(setState); return () => _modalListeners.delete(setState); }, []);
  if (!state) return null;
  return (
    <div className="modal-backdrop" onClick={modal.close}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>{state.content}</div>
    </div>
  );
}

// ── Audit log store (in-memory, shared) ────────────────────
const _auditEvents = []; // {id, t, actor, kind, summary, details, ts}
const _auditListeners = new Set();
let _auditIdCounter = 0;
function _emitAudit() { _auditListeners.forEach((cb) => cb([..._auditEvents])); }
const auditLog = {
  log(actor, kind, summary, details = null) {
    const evt = {
      id: ++_auditIdCounter,
      t: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      ts: Date.now(),
      actor, kind, summary, details,
    };
    _auditEvents.unshift(evt);
    _emitAudit();
    return evt;
  },
  subscribe(cb) { _auditListeners.add(cb); return () => _auditListeners.delete(cb); },
  all() { return [..._auditEvents]; },
};

// ── Tiny download helper ───────────────────────────────────
function downloadBlob(content, filename, mime = "text/plain") {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ── Find & Replace modal content ───────────────────────────
function FindReplaceModal() {
  const [find, setFind] = useState("");
  const [replace, setReplace] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);

  async function applyAll() {
    if (!find) { toast.push("Enter a find term", { tone: "attn" }); return; }
    const r = await api.findReplace(find, replace);
    auditLog.log("You", "find_replace", `Replaced "${find}" → "${replace}" (${r.count} occurrences)`);
    toast.push(`Replaced ${r.count} occurrences`, { tone: "ok" });
    modal.close();
  }
  return (
    <div style={{ width: 480, padding: 20 }}>
      <h3 className="modal__title">Find &amp; Replace</h3>
      <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
        <label style={{ display: "grid", gap: 4, fontSize: 11, color: "var(--fg2)", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          Find
          <input value={find} onChange={(e) => setFind(e.target.value)} autoFocus style={{ padding: "8px 10px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-mono)", fontSize: 13 }} placeholder="search term…" />
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 11, color: "var(--fg2)", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          Replace with
          <input value={replace} onChange={(e) => setReplace(e.target.value)} style={{ padding: "8px 10px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-mono)", fontSize: 13 }} placeholder="replacement…" />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: "var(--fg2)" }}>
          <input type="checkbox" checked={caseSensitive} onChange={(e) => setCaseSensitive(e.target.checked)} />
          Case-sensitive
        </label>
        <div style={{ fontSize: 11, color: "var(--fg2)", fontStyle: "italic" }}>Scoped to current session · virtualized-aware</div>
      </div>
      <div className="modal__actions">
        <button className="btn btn--ghost" onClick={modal.close}>Cancel</button>
        <button className="btn btn--primary" onClick={applyAll}>Replace all</button>
      </div>
    </div>
  );
}

// ── Suggest improvement modal ──────────────────────────────
function SuggestImprovementModal({ onSubmit }) {
  const [title, setTitle] = useState("");
  const [surface, setSurface] = useState("Editor / Transcript");
  const [priority, setPriority] = useState("med");
  const [desc, setDesc] = useState("");

  async function submit() {
    if (!title) { toast.push("Title required", { tone: "attn" }); return; }
    const r = await api.submitImprovement({ title, surface, priority, desc });
    onSubmit && onSubmit({ id: r.id, title, surface, priority, description: desc });
    auditLog.log("You", "improvement_submitted", `Filed ${r.id}: ${title}`);
    toast.push(`Submitted as ${r.id}`, { tone: "ok" });
    modal.close();
  }

  return (
    <div style={{ width: 520, padding: 20 }}>
      <h3 className="modal__title">Suggest Improvement</h3>
      <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
        <label style={{ display: "grid", gap: 4, fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--fg2)" }}>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus style={{ padding: "8px 10px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", fontSize: 13 }} />
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--fg2)" }}>
          Surface
          <select value={surface} onChange={(e) => setSurface(e.target.value)} style={{ padding: "8px 10px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", fontSize: 13 }}>
            <option>Editor / Transcript</option>
            <option>Editor / Slide Rail</option>
            <option>Editor / Right Rail</option>
            <option>Sessions list</option>
            <option>Dashboard</option>
            <option>Upload</option>
            <option>Settings</option>
            <option>Audit</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--fg2)" }}>
          Priority
          <select value={priority} onChange={(e) => setPriority(e.target.value)} style={{ padding: "8px 10px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", fontSize: 13 }}>
            <option value="low">Low</option>
            <option value="med">Medium</option>
            <option value="high">High</option>
            <option value="crit">Critical</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--fg2)" }}>
          Description
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={4} style={{ padding: "8px 10px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", fontSize: 13, fontFamily: "inherit", resize: "vertical" }} />
        </label>
      </div>
      <div className="modal__actions">
        <button className="btn btn--ghost" onClick={modal.close}>Cancel</button>
        <button className="btn btn--primary" onClick={submit}>Submit</button>
      </div>
    </div>
  );
}

// ── Segment edit modal ─────────────────────────────────────
function SegmentEditModal({ seg, onSave }) {
  const [text, setText] = useState(seg.text);
  return (
    <div style={{ width: 600, padding: 20 }}>
      <h3 className="modal__title">Edit segment <code style={{ fontFamily: "var(--font-mono)", color: "var(--fg-link)", fontSize: 13 }}>{seg.id}</code></h3>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={6}
        autoFocus
        style={{ width: "100%", padding: "10px 12px", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", fontSize: 14, fontFamily: "inherit", lineHeight: 1.6, marginTop: 12, resize: "vertical" }}
      />
      <div className="modal__actions">
        <button className="btn btn--ghost" onClick={modal.close}>Cancel</button>
        <button className="btn btn--primary" onClick={() => { onSave(text); modal.close(); }}>Save</button>
      </div>
    </div>
  );
}

// ── Command palette (⌘K) ───────────────────────────────────
function CommandPalette() {
  const [q, setQ] = useState("");
  const routes = [
    { label: "Dashboard",         path: "/dashboard" },
    { label: "Sessions",          path: "/sessions" },
    { label: "Upload new session", path: "/upload" },
    { label: "Improvements",      path: "/improvements" },
    { label: "Settings",          path: "/settings" },
    { label: "Audit ledger",      path: "/audit" },
    { label: "GCS QA",            path: "/gcs" },
    { label: "Editor (demo)",     path: "/e/se_001" },
    { label: "SOP workflow",      path: "/e/se_001/sop" },
    { label: "Session detail (demo)", path: "/s/se_001" },
    { label: "Viewer (demo)",     path: "/v/se_004" },
    { label: "Processing (demo)", path: "/p/se_007" },
  ];
  const filtered = routes.filter((r) => !q || r.label.toLowerCase().includes(q.toLowerCase()));
  return (
    <div style={{ width: 520, padding: 0 }}>
      <input
        autoFocus
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search routes…"
        style={{ width: "100%", padding: "16px 20px", border: "none", borderBottom: "1px solid var(--border-subtle)", fontSize: 16, fontFamily: "inherit", outline: "none" }}
      />
      <div style={{ maxHeight: 360, overflowY: "auto", padding: 6 }}>
        {filtered.map((r) => (
          <button key={r.path} onClick={() => { modal.close(); navigate(r.path); }}
            style={{ display: "flex", justifyContent: "space-between", width: "100%", padding: "10px 14px", border: "none", background: "transparent", textAlign: "left", fontFamily: "inherit", fontSize: 13, cursor: "pointer", borderRadius: 6 }}
            onMouseEnter={(e) => e.currentTarget.style.background = "var(--surface-muted)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
            <span style={{ color: "var(--fg1)" }}>{r.label}</span>
            <code style={{ color: "var(--fg2)", fontFamily: "var(--font-mono)", fontSize: 11 }}>{r.path}</code>
          </button>
        ))}
        {filtered.length === 0 ? (
          <div style={{ padding: 20, textAlign: "center", color: "var(--fg2)", fontSize: 12 }}>No matches</div>
        ) : null}
      </div>
    </div>
  );
}

// ── Wired-action helpers used everywhere ───────────────────
const wired = {
  exportCSV: async () => {
    toast.push("Generating CSV…");
    await api.exportCSV();
    downloadBlob("code,title,stage,assignee\nse_001,demo,copy_draft,KS\n", "sessions.csv", "text/csv");
    toast.push("CSV downloaded", { tone: "ok" });
  },
  download: async (kind, id) => {
    toast.push(`Preparing .${kind}…`);
    const r = await api.download(kind, id);
    auditLog.log("You", "export", `Downloaded ${kind} for ${id}`);
    downloadBlob(`Mock ${kind} export for ${id}\n`, `${id}.${kind}`, "text/plain");
    toast.push(`.${kind} downloaded`, { tone: "ok" });
  },
  logout: async () => {
    const ok = await confirm.open({
      title: "Sign out?",
      body: "You'll be redirected to login. Unsaved drafts are auto-saved.",
      confirmLabel: "Sign out",
    });
    if (!ok) return;
    auditLog.log("You", "auth", "Signed out");
    toast.push("Signed out", { tone: "ok" });
    navigate("/login");
  },
  fontSize: (delta) => {
    const cur = parseInt(document.documentElement.style.fontSize) || 16;
    const next = Math.max(12, Math.min(22, cur + delta));
    document.documentElement.style.fontSize = `${next}px`;
    toast.push(`Font ${delta > 0 ? "increased" : "decreased"} (${next}px)`);
  },
  openCmdK: () => modal.open(<CommandPalette />),
  openFind: () => modal.open(<FindReplaceModal />),
  openSuggestImprovement: (onSubmit) => modal.open(<SuggestImprovementModal onSubmit={onSubmit} />),
  openSegmentEdit: (seg, onSave) => modal.open(<SegmentEditModal seg={seg} onSave={onSave} />),

  advanceStage: async (sessionTitle, fromName, toName) => {
    const ok = await confirm.open({
      title: `Advance to ${toName}?`,
      body: `This will notify the next assignee and lock the ${fromName} stage. ${sessionTitle ? `Session: "${sessionTitle.slice(0, 60)}…"` : ""}`,
      confirmLabel: "Advance",
    });
    if (!ok) return false;
    await api.advanceStage("se_001", fromName, toName);
    auditLog.log("You", "stage_advance", `Advanced "${sessionTitle}": ${fromName} → ${toName}`);
    toast.push(`Advanced to ${toName}`, { tone: "ok" });
    return true;
  },
  deleteRow: async (label, onDelete) => {
    const ok = await confirm.open({
      title: `Delete ${label}?`,
      body: "Moved to Settings → Deleted sessions (recoverable for 30 days).",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return false;
    await api.deleteRow(label);
    auditLog.log("You", "delete", `Deleted ${label}`);
    onDelete && onDelete();
    toast.push(`${label} deleted`, {
      tone: "ok",
      action: { label: "Undo", onClick: () => toast.push(`${label} restored`, { tone: "ok" }) },
    });
    return true;
  },
  saveSetting: (label) => async () => {
    toast.push(`Saving ${label}…`);
    await api.saveSetting(label);
    auditLog.log("You", "settings", `Saved ${label}`);
    toast.push(`${label} saved`, { tone: "ok" });
  },
  testEmail: async () => {
    toast.push("Sending test email…");
    await api.testEmail();
    toast.push("Test email sent — check inbox", { tone: "ok" });
  },
  openGCS: (sid) => {
    toast.push("Opening GCS console (mock)", { tone: "info" });
    auditLog.log("You", "external", `Opened GCS console for ${sid}`);
  },
  cancelIngestion: async (sid) => {
    const ok = await confirm.open({
      title: "Cancel ingestion?",
      body: "Partial uploads will be discarded. This cannot be undone.",
      confirmLabel: "Cancel ingestion",
      danger: true,
    });
    if (!ok) return;
    await api.cancelIngestion(sid);
    auditLog.log("You", "cancel", `Canceled ingestion ${sid}`);
    toast.push("Ingestion canceled", { tone: "attn" });
  },
  resolveCheck: async (label) => {
    await api.resolveCheck(label);
    auditLog.log("You", "resolve", `Resolved check: ${label}`);
    toast.push(`Resolved: ${label}`, { tone: "ok" });
  },
  reassignStage: async (stageName) => {
    const next = window.prompt(`Assignee for ${stageName}?`, "Heather Howell");
    if (!next) return;
    auditLog.log("You", "reassign", `${stageName} reassigned to ${next}`);
    toast.push(`${stageName} → ${next}`, { tone: "ok" });
  },
  reassignSegment: async (seg) => {
    const next = window.prompt(`Move segment ${seg.id} to which slide number?`, "1");
    if (!next) return;
    auditLog.log("You", "reassign_segment", `Moved ${seg.id} → slide ${next}`);
    toast.push(`Moved to slide ${next}`, { tone: "ok" });
  },
  toastInfo: (msg, tone = "info") => toast.push(msg, { tone }),
};

Object.assign(window, {
  api, toast, useToasts, ToastHost,
  confirm, ConfirmHost,
  modal, ModalHost,
  auditLog,
  downloadBlob,
  FindReplaceModal, SuggestImprovementModal, SegmentEditModal, CommandPalette,
  wired,
});
