/* eslint-disable no-undef */
// Settings sub-pages — full inline drill-down for every section.
// Replaces the 2-card scaffold with production-parity functional UI.

// ── Shared fixture data ───────────────────────────────────
const TEAM_PEOPLE = [
  { name: "Carla Burris",      email: "carlab@vin.com" },
  { name: "Debbie Hembroff",   email: "hembroff@telus.net" },
  { name: "Erica Hulse",       email: "ericah@vin.com" },
  { name: "Heather Howell",    email: "HeatherH@vin.com" },
  { name: "Janet Stomberg",    email: "janet.stomberg@vin.com" },
  { name: "John Dean",         email: "john@vetvision.org" },
  { name: "Lacy Sanders",      email: "lacy.sanders@vin.com" },
  { name: "Rachalel Carpenter",email: "rachael@vin.com" },
  { name: "Ruth Schoonover",   email: "ruth@vin.com" },
  { name: "Tina Payton",       email: "tina.payton@vin.com" },
];
const TEAM_GROUPS = [
  { name: "Content Team",     members: ["Carla Burris", "Heather Howell", "Ruth Schoonover"] },
  { name: "Debbie (and Team)", members: ["Debbie Hembroff"] },
  { name: "External",         members: ["Carla Burris", "Heather Howell", "Ruth Schoonover"] },
  { name: "Main Contact",     members: ["Carla Burris"] },
  { name: "V@V",              members: ["Carla Burris"] },
];
const SESSION_TYPES = [
  "default", "AAFV", "ABVP", "AEMV", "ARAV", "Cytology Cafe", "Euro", "FelineVMA",
  "IVAPM", "IVFSA", "IVPA", "NAVAS", "Therio", "Tuesday Topic", "VECCS",
  "VVI Cage-Side", "VVI Cage-Side Radiology Rounds",
];
const AI_MODELS = [
  { v: "gemini-2.5-pro",          label: "Gemini 2.5 Pro (recommended)" },
  { v: "gemini-2.5-pro-preview",  label: "Gemini 2.5 Pro Preview (June)" },
  { v: "gemini-2.5-flash",        label: "Gemini 2.5 Flash" },
  { v: "gemini-2.5-flash-prev",   label: "Gemini 2.5 Flash Preview (Apr)" },
  { v: "gemini-2.0-flash",        label: "Gemini 2.0 Flash" },
  { v: "gemini-2.0-flash-lite",   label: "Gemini 2.0 Flash Lite" },
  { v: "gemini-1.5-pro",          label: "Gemini 1.5 Pro" },
  { v: "gemini-1.5-flash",        label: "Gemini 1.5 Flash" },
];
const PROMPT_TEMPLATES = [
  { id: "lecture",  cat: "Education",      icon: "🎓", name: "Lecture",            desc: "Optimized for structured teaching content",     chips: ["strict","neutral","medium","structure","key points"] },
  { id: "training", cat: "Education",      icon: "🛠️", name: "Training / Workshop", desc: "Handles Q&A, exercises and interaction patterns", chips: ["moderate","preserve","medium","structure","key points"] },
  { id: "technical", cat: "Technical",     icon: "⚙️", name: "Technical Deep Dive", desc: "Terminology preservation — minimal rewrite",     chips: ["moderate","preserve","strict","structure","key points"] },
  { id: "podcast",  cat: "Conversational", icon: "🎙️", name: "Podcast / Conversation", desc: "Light cleanup — conversational flow preserved", chips: ["light","conversational","low"] },
  { id: "sales",    cat: "Business",       icon: "📊", name: "Sales / Presentation", desc: "Emphasis and persuasion patterns preserved",    chips: ["moderate","persuasive","medium","structure","key points"] },
  { id: "custom",   cat: "Custom",         icon: "⚡", name: "Custom",             desc: "Define your own processing rules",              chips: ["moderate","neutral","medium","structure","key points"] },
];
const SOP_STAGE_KEYS = [
  { id: "prep",        label: "Prep (optional)" },
  { id: "copy_draft",  label: "Copy Edit — Draft" },
  { id: "medical",     label: "Medical Review" },
  { id: "copy_final",  label: "Copy Edit — Final" },
  { id: "cms",         label: "CMS Transcript Published" },
  { id: "captions",    label: "Captions on Video" },
  { id: "qa",          label: "QA" },
  { id: "complete",    label: "Complete (auto-advances)" },
];

// ── Section renderers ─────────────────────────────────────

function SectionGeneral() {
  const [name, setName] = useState("VIN VIN Transcript Software");
  const [tz, setTz] = useState("America/Chicago");
  const [locale, setLocale] = useState("en-US");
  return (
    <>
      <SettingsHeader title="General" lead="Workspace identity, default locale, and time zone." />
      <div className="set-form">
        <FormRow label="Organisation name"><input className="set-input" value={name} onChange={(e) => setName(e.target.value)} /></FormRow>
        <FormRow label="Default locale"><select className="set-input" value={locale} onChange={(e) => setLocale(e.target.value)}><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option><option value="es-ES">Spanish</option></select></FormRow>
        <FormRow label="Time zone"><select className="set-input" value={tz} onChange={(e) => setTz(e.target.value)}><option value="America/Chicago">America/Chicago (CT)</option><option value="America/Los_Angeles">America/Los_Angeles (PT)</option><option value="America/New_York">America/New_York (ET)</option><option value="Europe/London">Europe/London (GMT)</option></select></FormRow>
        <div className="set-form__actions">
          <button className="btn btn--primary" onClick={() => { auditLog.log("You","settings","Saved General"); toast.push("General saved",{tone:"ok"}); }}>Save</button>
        </div>
      </div>
    </>
  );
}

function SectionTeam() {
  const [people, setPeople] = useState([...TEAM_PEOPLE]);
  const [groups, setGroups] = useState([...TEAM_GROUPS]);
  const [newGroup, setNewGroup] = useState("");
  return (
    <>
      <SettingsHeader title="Team & roles" lead="People who can be assigned stages, and groups used for routing." />
      <div className="set-twocol">
        <div className="set-pane">
          <div className="set-pane__head">
            <span className="set-eyebrow">PEOPLE · {people.length}</span>
            <button className="btn btn--tertiary" onClick={() => {
              const n = window.prompt("Name?"); if (!n) return;
              const e = window.prompt("Email?") || "";
              setPeople([...people, { name: n, email: e }]);
              auditLog.log("You","settings",`Added person ${n}`);
              toast.push(`${n} added`, {tone:"ok"});
            }}>+ Add person</button>
          </div>
          {people.map((p, i) => (
            <div key={i} className="set-row">
              <div>
                <div className="set-row__name">{p.name}</div>
                <div className="set-row__sub">{p.email}</div>
              </div>
              <div className="set-row__actions">
                <button className="set-link" onClick={() => { const n = window.prompt("Name?", p.name); if (!n) return; setPeople(people.map((x,j) => j===i ? {...x, name:n} : x)); toast.push("Updated",{tone:"ok"}); }}>Edit</button>
                <button className="set-link set-link--danger" onClick={async () => { const ok = await confirm.open({ title:`Delete ${p.name}?`, danger:true, confirmLabel:"Delete" }); if (!ok) return; setPeople(people.filter((_,j) => j!==i)); auditLog.log("You","settings",`Deleted person ${p.name}`); toast.push(`${p.name} deleted`,{tone:"ok"}); }}>Delete</button>
              </div>
            </div>
          ))}
        </div>
        <div className="set-pane">
          <div className="set-pane__head">
            <span className="set-eyebrow">GROUPS · {groups.length}</span>
            <span style={{ display:"inline-flex", gap:6 }}>
              <input className="set-input set-input--sm" placeholder="New group name" value={newGroup} onChange={(e)=>setNewGroup(e.target.value)} />
              <button className="btn btn--tertiary" onClick={() => { if (!newGroup) return; setGroups([...groups, { name:newGroup, members:[] }]); auditLog.log("You","settings",`Added group ${newGroup}`); toast.push(`${newGroup} added`,{tone:"ok"}); setNewGroup(""); }}>+ Add</button>
            </span>
          </div>
          {groups.map((g, gi) => (
            <div key={gi} className="set-row set-row--col">
              <div className="set-row__top">
                <div className="set-row__name">{g.name}</div>
                <button className="set-link set-link--danger" onClick={async () => { const ok = await confirm.open({title:`Delete group ${g.name}?`,danger:true,confirmLabel:"Delete"}); if(!ok) return; setGroups(groups.filter((_,i)=>i!==gi)); toast.push("Group deleted",{tone:"ok"}); }}>Delete</button>
              </div>
              <div className="set-chip-row">
                {g.members.map((m, mi) => (
                  <span key={mi} className="chip chip--blue">{m} <button className="set-chip-x" onClick={()=>{ setGroups(groups.map((x,i)=> i===gi ? {...x, members:x.members.filter((_,j)=>j!==mi)} : x)); }}>×</button></span>
                ))}
                <select className="set-input set-input--sm" defaultValue="" onChange={(e) => { if (!e.target.value) return; if (g.members.includes(e.target.value)) return; setGroups(groups.map((x,i)=> i===gi ? {...x, members:[...x.members, e.target.value]} : x)); e.target.value=""; }}>
                  <option value="">+ Add member</option>
                  {people.filter((p) => !g.members.includes(p.name)).map((p)=>(<option key={p.email} value={p.name}>{p.name}</option>))}
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function SectionTypes() {
  const [types, setTypes] = useState([...SESSION_TYPES]);
  const [active, setActive] = useState("default");
  const [newType, setNewType] = useState("");
  const allAssignees = ["(unassigned)", ...TEAM_PEOPLE.map((p)=>p.name), "Group: Content Team", "Group: External", "Group: V@V", "Group: Main Contact"];
  const defaultAssignees = { prep:"Tina Payton", copy_draft:"Tina Payton", medical:"Group: External", copy_final:"Tina Payton", cms:"Tina Payton", captions:"Erica Hulse", qa:"Lacy Sanders", complete:"Carla Burris" };
  const [matrix, setMatrix] = useState({ ...defaultAssignees });
  const [emails, setEmails] = useState({ complete: true });

  return (
    <>
      <SettingsHeader title="Types & stage defaults" lead="Each Type defines a default assignee and notify-on-entry flag per stage. New sessions auto-populate from the selected Type's matrix row." />
      <div className="set-twocol set-twocol--340">
        <div className="set-pane">
          <div className="set-pane__head">
            <input className="set-input set-input--sm" placeholder="New Type name" value={newType} onChange={(e) => setNewType(e.target.value)} />
            <button className="btn btn--tertiary" onClick={() => { if (!newType) return; setTypes([...types, newType]); setActive(newType); auditLog.log("You","settings",`Added type ${newType}`); toast.push(`${newType} added`,{tone:"ok"}); setNewType(""); }}>+ Add type</button>
          </div>
          {types.map((t) => (
            <div key={t} className={`set-row set-row--clickable ${active === t ? "is-active" : ""}`} onClick={() => setActive(t)}>
              <span>{t}{t === "default" ? <span className="set-default-pill">DEFAULT</span> : null}</span>
              {t !== "default" ? (
                <button className="set-link set-link--danger" onClick={async (e) => { e.stopPropagation(); const ok = await confirm.open({title:`Remove ${t}?`,danger:true,confirmLabel:"Remove"}); if(!ok) return; setTypes(types.filter(x=>x!==t)); if(active===t) setActive("default"); toast.push("Type removed",{tone:"ok"}); }}>Remove</button>
              ) : null}
            </div>
          ))}
        </div>
        <div className="set-pane">
          <div className="set-pane__head">
            <span className="set-eyebrow">STAGE ASSIGNEES FOR <strong style={{ color: "var(--fg1)" }}>{active}</strong></span>
          </div>
          {SOP_STAGE_KEYS.map((s) => (
            <div key={s.id} className="set-matrix-row">
              <label>{s.label}</label>
              <select className="set-input" value={matrix[s.id] || "(unassigned)"} onChange={(e) => setMatrix({ ...matrix, [s.id]: e.target.value })}>
                {allAssignees.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
              <label className="set-matrix-row__email"><input type="checkbox" checked={!!emails[s.id]} onChange={(e) => setEmails({ ...emails, [s.id]: e.target.checked })} /> Email</label>
            </div>
          ))}
          <div style={{ textAlign: "right", marginTop: 14 }}>
            <button className="btn btn--tertiary" onClick={() => { auditLog.log("You","settings",`Saved matrix for ${active}`); toast.push("Matrix saved",{tone:"ok"}); }}>Save matrix</button>
          </div>
        </div>
      </div>
    </>
  );
}

function SectionAIModels() {
  const [model, setModel] = useState("gemini-2.5-pro");
  return (
    <>
      <SettingsHeader title="AI models" lead="Default model used for new AI MODE sessions. Can be overridden per session on Upload." />
      <div className="set-form">
        <FormRow label="Default AI model" sub="Model used for transcription and discrepancy passes.">
          <select className="set-input" value={model} onChange={(e) => { setModel(e.target.value); toast.push(`Model: ${AI_MODELS.find(m=>m.v===e.target.value)?.label}`,{tone:"ok"}); }}>
            {AI_MODELS.map((m) => <option key={m.v} value={m.v}>{m.label}</option>)}
          </select>
        </FormRow>
      </div>
    </>
  );
}

function SectionUpload() {
  const [method, setMethod] = useState("railway");
  return (
    <>
      <SettingsHeader title="Upload & storage" lead="How large files are transferred to our processing pipeline." />
      <div className="set-form">
        <FormRow label="Upload method"
                 sub="Railway routes file bytes through our server (current default). GCS sends bytes directly from your browser to cloud storage, bypassing the server — more reliable on slow connections and for large files.">
          <select className="set-input" value={method} onChange={(e) => { setMethod(e.target.value); toast.push("Upload method updated",{tone:"ok"}); }}>
            <option value="railway">Railway (default)</option>
            <option value="gcs">GCS (direct upload)</option>
          </select>
        </FormRow>
      </div>
    </>
  );
}

function SectionDiscrepancy() {
  const [backend, setBackend] = useState("gemini-dev");
  const [model, setModel] = useState("gemini-2.0-flash");
  return (
    <>
      <SettingsHeader title="Discrepancy classification" lead="Classifier used to tag discrepancies by type (medication, terminology, etc.). Separate from the main pipeline model — change freely without affecting transcription." />
      <div className="set-form">
        <FormRow label="Classification backend"
                 sub="Gemini API uses your GEMINI_API_KEY. Vertex AI Gemini uses a separate API key (VERTEX_AI_GEMINI_API_KEY) with independent billing and quota.">
          <select className="set-input" value={backend} onChange={(e) => setBackend(e.target.value)}>
            <option value="gemini-dev">Gemini Developer API</option>
            <option value="vertex">Vertex AI Gemini (separate billing)</option>
          </select>
        </FormRow>
        <FormRow label="Classification AI model"
                 sub="Model used to classify discrepancies. Change freely without affecting transcription.">
          <select className="set-input" value={model} onChange={(e) => setModel(e.target.value)}>
            {AI_MODELS.map((m) => <option key={m.v} value={m.v}>{m.label}</option>)}
          </select>
        </FormRow>
        <div className="set-callout">Default: Gemini 2.0 Flash. If 503 errors persist, switch to Vertex AI backend.</div>
      </div>
    </>
  );
}

function SectionExport() {
  const [keyPoints, setKeyPoints] = useState(false);
  return (
    <>
      <SettingsHeader title="Export" lead="What gets included when you download a session." />
      <div className="set-form">
        <FormRow label="Include key points"
                 sub="Add suggested key points to exported documents."
                 control={<TogglePill on={keyPoints} onChange={setKeyPoints} />} />
        <div className="set-card-block">
          <div className="set-eyebrow">WORD MACRO (ONE-TIME INSTALL)</div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14, marginTop: 8 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--fg1)" }}>Download <code style={{ fontFamily:"var(--font-mono)", fontSize: 12.5 }}>macro_COMPLETE_v5.zip</code></div>
              <div style={{ fontSize: 12.5, color: "var(--fg2)", lineHeight: 1.55, marginTop: 4 }}>
                VBA macros <code>SRT_Transcript</code> and <code>CMS_Transcript</code> that clean the downloaded <code>.docx</code> for Wistia SRT and CMS publishing. Unzip once, then open in Word → Developer → Visual Basic → Import.
              </div>
            </div>
            <button className="btn btn--tertiary" onClick={() => { downloadBlob("' VBA macro placeholder", "macro_COMPLETE_v5.zip", "application/zip"); toast.push("Macro downloaded",{tone:"ok"}); }}>↓ Download (.zip)</button>
          </div>
        </div>
      </div>
    </>
  );
}

function SectionPromptTemplates() {
  const [view, setView] = useState("catalog"); // catalog | new
  if (view === "new") return <PromptTemplatesNew onCancel={() => setView("catalog")} onSave={() => { setView("catalog"); toast.push("Template saved",{tone:"ok"}); }} />;
  return <PromptTemplatesCatalog onNew={() => setView("new")} />;
}

function PromptTemplatesCatalog({ onNew }) {
  const cats = ["Education", "Technical", "Conversational", "Business", "Custom"];
  return (
    <>
      <div className="set-subnav">
        <button className="set-link" onClick={() => wired.toastInfo("Back to Settings")}>← Settings</button>
        <h2 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>Templates</h2>
        <button className="btn sugg-modal__submit" style={{ marginLeft: "auto" }} onClick={onNew}>+ New Template</button>
      </div>
      <h3 className="set-section-title" style={{ marginTop: 12 }}>Processing Templates (STT Pipeline)</h3>
      <p style={{ color:"var(--fg2)", fontSize:13, margin:"0 0 18px" }}>Control filler removal, tone, terminology for standard speech-to-text processing</p>
      {cats.map((cat) => {
        const items = PROMPT_TEMPLATES.filter((t) => t.cat === cat);
        if (!items.length) return null;
        return (
          <div key={cat} style={{ marginBottom: 18 }}>
            <div className="set-eyebrow" style={{ marginBottom: 8 }}>{cat.toUpperCase()}</div>
            {items.map((t) => (
              <div key={t.id} className="set-tpl-card">
                <div style={{ fontSize: 22 }}>{t.icon}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="set-tpl-card__name">{t.name}</div>
                  <div className="set-tpl-card__desc">{t.desc}</div>
                  <div className="set-tpl-card__chips">{t.chips.map((c) => <code key={c}>{c}</code>)}</div>
                </div>
                <span className="set-tpl-card__tag set-tpl-card__tag--iil">IIL</span>
                <span className="set-tpl-card__tag">System</span>
                {t.id === "custom" ? (
                  <button className="set-link" onClick={() => wired.toastInfo("Editing Custom template (mock)")}>Edit</button>
                ) : (
                  <button className="set-link" onClick={() => { toast.push(`Duplicated ${t.name}`,{tone:"ok"}); }}>Duplicate</button>
                )}
              </div>
            ))}
          </div>
        );
      })}
      <h3 className="set-section-title" style={{ marginTop: 28 }}>AI Prompt Templates (Gemini)</h3>
      <p style={{ color:"var(--fg2)", fontSize:13, margin:"0 0 18px" }}>Define the system prompt sent to Gemini for AI MODE processing</p>
      <div className="set-tpl-card">
        <div style={{ fontSize: 22 }}>📝</div>
        <div style={{ flex: 1 }}>
          <div className="set-tpl-card__name">Transcript</div>
          <div className="set-tpl-card__desc">Clean, enhanced transcript with corrected speech errors</div>
          <pre className="set-tpl-card__code">You are generating a VIN transcript that must be 100% compliant with the full Transcript SOP and downstream processing.p.</pre>
        </div>
        <span className="set-tpl-card__tag set-tpl-card__tag--iil">Prompt</span>
        <span className="set-tpl-card__tag">System</span>
        <button className="set-link" onClick={() => wired.toastInfo("Viewing template")}>View</button>
        <button className="set-link" onClick={() => toast.push("Duplicated Transcript",{tone:"ok"})}>Duplicate</button>
      </div>
      <div className="set-tpl-card">
        <div style={{ fontSize: 22 }}>📝</div>
        <div style={{ flex: 1 }}>
          <div className="set-tpl-card__name">Transcript (Paragraph v1)</div>
          <div className="set-tpl-card__desc">Clean, enhanced transcript with corrected speech errors</div>
        </div>
        <span className="set-tpl-card__tag set-tpl-card__tag--iil">Prompt</span>
        <button className="set-link" onClick={() => wired.toastInfo("Editing template")}>Edit</button>
      </div>
    </>
  );
}

function PromptTemplatesNew({ onCancel, onSave }) {
  const [type, setType] = useState("processing");
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("📝");
  const [desc, setDesc] = useState("");
  const [cat, setCat] = useState("Custom");
  const [filler, setFiller] = useState("Moderate");
  const [tone, setTone] = useState("Neutral");
  const [term, setTerm] = useState("Medium");
  const [rewrite, setRewrite] = useState("Minimal");
  const [structure, setStructure] = useState(true);
  const [keypoints, setKeypoints] = useState(true);
  const [prompt, setPrompt] = useState("");

  return (
    <>
      <div className="set-subnav">
        <button className="set-link" onClick={onCancel}>← Settings</button>
        <h2 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>Templates</h2>
        <button className="btn sugg-modal__submit" style={{ marginLeft: "auto" }}>+ New Template</button>
      </div>
      <div className="set-pane" style={{ padding: 22 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>New Template</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn--secondary" onClick={onCancel}>Cancel</button>
            <button className="btn sugg-modal__submit" onClick={onSave}>Save</button>
          </div>
        </div>
        <FormRow label="Type">
          <select className="set-input" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="processing">Processing Template (STT/IIL)</option>
            <option value="ai-prompt">AI Prompt Template (Gemini)</option>
          </select>
        </FormRow>
        <FormRow label="Name"><input className="set-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Template name" /></FormRow>
        <FormRow label="Icon"><input className="set-input" value={icon} onChange={(e) => setIcon(e.target.value)} style={{ maxWidth: 80 }} /></FormRow>
        <FormRow label="Description"><input className="set-input" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Brief description" /></FormRow>
        <FormRow label="Category">
          <select className="set-input" value={cat} onChange={(e) => setCat(e.target.value)}>
            <option>Education</option><option>Technical</option><option>Conversational</option><option>Business</option><option>Custom</option>
          </select>
        </FormRow>

        <div className="set-eyebrow" style={{ marginTop: 24, marginBottom: 14, color: "var(--text-accent)" }}>IIL CONFIGURATION</div>
        <FormRow label="Filler policy"><select className="set-input" value={filler} onChange={(e) => setFiller(e.target.value)}><option>Strict</option><option>Moderate</option><option>Light</option></select></FormRow>
        <FormRow label="Tone"><select className="set-input" value={tone} onChange={(e) => setTone(e.target.value)}><option>Neutral</option><option>Conversational</option><option>Formal</option><option>Persuasive</option></select></FormRow>
        <FormRow label="Terminology"><select className="set-input" value={term} onChange={(e) => setTerm(e.target.value)}><option>Strict</option><option>Medium</option><option>Loose</option></select></FormRow>
        <FormRow label="Rewrite level"><select className="set-input" value={rewrite} onChange={(e) => setRewrite(e.target.value)}><option>Minimal</option><option>Moderate</option><option>Aggressive</option></select></FormRow>
        <FormRow label="Structure extraction" control={<TogglePill on={structure} onChange={setStructure} />} />
        <FormRow label="Key points" control={<TogglePill on={keypoints} onChange={setKeypoints} />} />

        <div className="set-eyebrow" style={{ marginTop: 24, marginBottom: 6 }}>SYSTEM PROMPT</div>
        <div style={{ fontSize: 12, color: "var(--fg2)", marginBottom: 8 }}>The prompt sent to Gemini for AI MODE processing. Leave empty to use the default.</div>
        <textarea className="set-input" rows={8} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Enter system prompt." style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, lineHeight: 1.6, resize: "vertical" }} />
        <div style={{ textAlign: "right", fontSize: 11, color: "var(--fg2)", marginTop: 4 }}>{prompt.length} characters</div>
      </div>
    </>
  );
}

function SectionManifest() {
  const fields = [
    { f: "session code = …", desc: "filename prefix + session code badge" },
    { f: "long title = / short title = …", desc: "session header titles" },
    { f: "*Moderator = … + Bio", desc: "speaker records (moderator = primary)" },
    { f: "CE Broker / VIN# fields", desc: "CE metadata badges" },
    { f: "Zoom = …, Session pg = …, Podbean, VINcast, MB", desc: "publishing links" },
    { f: "@N blocks with URLs", desc: "per-slide resource icons in Editor slide rail" },
    { f: "Tags: …", desc: "category chips" },
    { f: "Polls section", desc: "parsed by polls regex into polls_parsed JSONB" },
  ];
  return (
    <>
      <SettingsHeader title="Session manifest (extras2)" lead="Upload a producer-prepared extras2.txt alongside the video/audio to auto-populate speaker labels, per-slide resources, and publishing links in the exported .docx. Optional — sessions without it still export cleanly." />
      <div className="set-eyebrow" style={{ marginBottom: 12 }}>EXPECTED FIELDS <span style={{ color: "var(--fg2)", marginLeft: 6, textTransform: "none", letterSpacing: 0, fontWeight: 500 }}>· pure regex parsing, no AI</span></div>
      <div className="set-manifest">
        {fields.map((f, i) => (
          <div key={i} className="set-manifest__row">
            <code>{f.f}</code>
            <span>{f.desc}</span>
          </div>
        ))}
      </div>
      <div className="set-eyebrow" style={{ marginTop: 22, marginBottom: 8 }}>FILENAME CONVENTIONS</div>
      <p style={{ fontSize: 13, color: "var(--fg1)", lineHeight: 1.6, margin: 0 }}>
        Any <code>.txt</code> whose name matches <code>*extras2*</code>, <code>*_manifest*</code>, or starts with <code>manifest_</code> is auto-routed to the manifest slot on upload. Otherwise drop any <code>.txt</code> in the upload dropzone and re-tag it.
      </p>
    </>
  );
}

function SectionEmail() {
  const [view, setView] = useState("home"); // home | builder
  if (view === "builder") return <EmailBuilder onBack={() => setView("home")} />;
  return (
    <>
      <SettingsHeader title="Email templates" lead="Per-Type × per-Stage stage-notification HTML templates. Edit in the dedicated builder." headerCta={{ label: "Open builder", onClick: () => setView("builder") }} />
      <div className="set-card-block">
        <div className="set-eyebrow">STAGE ASSIGNEES + NOTIFY-ON-ENTRY CHECKBOXES</div>
        <h4 style={{ margin: "6px 0 6px", fontSize: 16, fontWeight: 700 }}>Stage triggers via Types matrix</h4>
        <p style={{ fontSize: 13, color: "var(--fg2)", lineHeight: 1.6, margin: 0 }}>
          Stage-level email triggers live in the <strong>Types & stage defaults</strong> matrix per Type. Each stage has a default assignee (person or group) and an optional <em>Email</em> toggle that fires the stage-notification template on entry.
        </p>
      </div>
      <div className="set-card-block">
        <div className="set-eyebrow">ADMIN · TEST EMAIL</div>
        <h4 style={{ margin: "6px 0 6px", fontSize: 16, fontWeight: 700 }}>Email send diagnostics</h4>
        <p style={{ fontSize: 13, color: "var(--fg2)", lineHeight: 1.6, margin: 0 }}>Check SMTP config, test connectivity, and send a test email. Copyable diagnostic bundle for support tickets.</p>
      </div>
    </>
  );
}

function EmailBuilder({ onBack }) {
  const stages = [
    { id: "prep",        label: "1 Prep" },
    { id: "copy_draft",  label: "2 Copy edit — draft" },
    { id: "medical",     label: "3 Medical review" },
    { id: "copy_final",  label: "4 Copy edit — final" },
    { id: "cms",         label: "5 CMS published" },
    { id: "captions",    label: "6 Captions on video" },
    { id: "qa",          label: "7 QA" },
    { id: "complete",    label: "8 Complete" },
  ];
  // Per-stage default templates — all VIN-Transcript-Software-branded.
  const DEFAULTS = {
    prep:        { subject: "[VIN] Ready for prep — {{ session_code }}",        body: `<!DOCTYPE html>\n<html><body style="margin:0;padding:0;background:#F7F7F7;font-family:'ProximaNova',Helvetica,Arial,sans-serif;color:#002855;">\n  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <tr><td style="background:#002855;padding:20px 28px;color:#FFFFFF;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Ready for prep · {{ session_code }}</div>\n    </td></tr>\n    <tr><td style="padding:18px 28px;background:#F9FAFB;font-family:'Courier New',monospace;font-size:12px;color:#4D6995;line-height:1.7;border-bottom:1px solid #DDE5ED;">\n      Uploaded {{ session_uploaded_at }} · {{ segment_count }} segments · {{ slide_count }} slides · {{ speaker_count }} speakers\n    </td></tr>\n    <tr><td style="padding:24px 28px;font-size:14px;line-height:1.6;color:#002855;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>A new session has been uploaded and is ready for your prep review. Before copy edit can begin, please verify the extras and confirm everything needed is present.</p>\n      <p style="margin:18px 0 6px;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#4D6995;">WHAT TO DO</p>\n      <ol style="margin:0 0 18px;padding-left:20px;font-size:14px;line-height:1.7;">\n        <li>Open the session and verify slides, chat, and polls are all present.</li>\n        <li>Confirm the session code and title are correct.</li>\n        <li>Flag any missing extras or malformed input.</li>\n        <li>When ready, mark <strong>Prep complete</strong> to hand off to copy edit.</li>\n      </ol>\n      <p><a href="{{ results_url }}" style="display:inline-block;background:#002855;color:#FFFFFF;padding:11px 22px;border-radius:8px;font-weight:600;text-decoration:none;">Open session →</a></p>\n    </td></tr>\n    <tr><td style="padding:14px 28px;background:#F7F7F7;font-size:11px;color:#4D6995;border-top:1px solid #DDE5ED;">\n      Sent by VIN Transcript Software · Reply to this email with questions\n    </td></tr>\n  </table>\n</body></html>` },
    copy_draft:  { subject: "[VIN] Ready to copy edit — {{ session_code }}",     body: `<!-- VIN Transcript Software · Stage 2 ·  Copy edit draft -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;padding:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Ready to copy edit · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;line-height:1.65;color:#002855;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>{{ prior_actor_full_name }} has finished prep on {{ session_code }}. It's ready for your draft copy edit in the AI editor.</p>\n      <p>Open the editor → work through flagged review items → mark <strong>Copy edit — draft complete</strong>.</p>\n      <p><a href="{{ editor_url }}" style="display:inline-block;background:#002855;color:#FFFFFF;padding:11px 22px;border-radius:8px;font-weight:600;text-decoration:none;">Open editor →</a></p>\n    </div>\n  </div>\n</body></html>` },
    medical:     { subject: "[VIN] Medical review requested — {{ session_code }}", body: `<!-- VIN Transcript Software · Stage 3 · Medical review -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;padding:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Medical review requested · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;line-height:1.65;color:#002855;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>The draft transcript for {{ session_code }} — <em>{{ session_title }}</em> — is ready for your medical review. Please review with tracked changes enabled and return it to {{ prior_actor_full_name }} when complete.</p>\n      <p><strong>What to do</strong></p>\n      <ol style="padding-left:20px;line-height:1.7;">\n        <li>Open the Word document.</li>\n        <li>Turn on <strong>Track Changes</strong> before editing.</li>\n        <li>Focus on medical accuracy, terminology, and factual corrections.</li>\n        <li>Save and send the reviewed document back to {{ prior_actor_full_name }}.</li>\n      </ol>\n    </div>\n  </div>\n</body></html>` },
    copy_final:  { subject: "[VIN] Final copy edit pass — {{ session_code }}",   body: `<!-- VIN Transcript Software · Stage 4 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Final copy edit · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>Medical review is complete. Incorporate the medical reviewer's notes, finalize speaker labels, and do the final readthrough.</p>\n    </div>\n  </div>\n</body></html>` },
    cms:         { subject: "[VIN] Ready for CMS publish — {{ session_code }}",  body: `<!-- VIN Transcript Software · Stage 5 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Publish to CMS · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>Final copy is complete. Generate the CMS-ready document, upload to VIN library, and attest CE hours.</p>\n    </div>\n  </div>\n</body></html>` },
    captions:    { subject: "[VIN] Captions ready for upload — {{ session_code }}", body: `<!-- VIN Transcript Software · Stage 6 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Captions ready · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>The transcript is published to CMS. The SRT file is ready for Wistia upload and burn-in.</p>\n      <ol style="padding-left:20px;line-height:1.7;">\n        <li>Download the SRT file.</li>\n        <li>Upload to Wistia for the session video.</li>\n        <li>Enable burn-in captions and verify playback.</li>\n        <li>Mark <strong>Captions on video complete</strong>.</li>\n      </ol>\n    </div>\n  </div>\n</body></html>` },
    qa:          { subject: "[VIN] QA pass requested — {{ session_code }}",     body: `<!-- VIN Transcript Software · Stage 7 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">QA pass · {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ assignee_first_name }},</p>\n      <p>The session is ready for QA. Run end-to-end playback spot checks, verify mobile rendering, confirm search indexing, and validate GCS G1–G14 checks pass.</p>\n    </div>\n  </div>\n</body></html>` },
    complete:    { subject: "[VIN] Session published · {{ session_code }}",     body: `<!-- VIN Transcript Software · Stage 8 -->\n<html><body style="font-family:'ProximaNova',sans-serif;background:#F7F7F7;margin:0;">\n  <div style="max-width:640px;margin:0 auto;background:#FFFFFF;">\n    <div style="background:#002855;color:#FFFFFF;padding:20px 28px;">\n      <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#B1C9E8;">VIN Transcript Software</div>\n      <div style="font-size:18px;font-weight:800;margin-top:4px;">Published — {{ session_code }}</div>\n    </div>\n    <div style="padding:24px 28px;font-size:14px;color:#002855;line-height:1.65;">\n      <p>Hi {{ prior_actor_full_name }},</p>\n      <p>{{ session_code }} is now live in the VIN library. Presenter notified, audit ledger archived. Thanks for the work.</p>\n    </div>\n  </div>\n</body></html>` },
  };
  const [stage, setStage] = useState("prep");
  const [type, setType] = useState("default · default");
  const [subject, setSubject] = useState(DEFAULTS.prep.subject);
  const [body, setBody] = useState(DEFAULTS.prep.body);
  // Switch templates when stage changes
  useEffect(() => { setSubject(DEFAULTS[stage].subject); setBody(DEFAULTS[stage].body); }, [stage]);

  const varCategories = [
    { name: "SESSION", vars: ["session_code", "session_title", "session_type_name", "session_uploaded_at", "session_duration_minutes"] },
    { name: "COUNTS",  vars: ["segment_count", "slide_count", "speaker_count", "chat_message_count", "poll_count"] },
    { name: "STAGE",   vars: ["stage_name", "stage_label_human", "stage_number", "total_stages", "prior_stage_label", "next_stage_label", "stage_color"] },
    { name: "ASSIGNEE", vars: ["assignee_first_name", "assignee_full_name", "assignee_initials", "assignee_email"] },
    { name: "ACTOR",    vars: ["prior_actor_full_name", "prior_actor_initials", "prior_actor_completed_at"] },
    { name: "LINKS",    vars: ["results_url", "editor_url", "session_page_url", "audit_trail_url", "cms_url", "video_url"] },
  ];

  const insertVar = (v) => setSubject((s) => s + ` {{ ${v} }}`);

  return (
    <>
      <div className="set-subnav">
        <button className="set-link" onClick={onBack}>← Settings</button>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Email Template Builder</h2>
        <span style={{ fontSize: 11, color: "var(--fg2)", marginLeft: 8 }}>Per Type × Stage · stage-notification emails sent from VIN Transcript Software</span>
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: 10, alignItems: "center" }}>
          <span className="set-eyebrow">EDITING</span>
          <select className="set-input set-input--sm" value={type} onChange={(e) => setType(e.target.value)} style={{ width: 240 }}>
            <option>default · default</option>
            {SESSION_TYPES.slice(1).map((t) => <option key={t}>{t}</option>)}
          </select>
        </span>
      </div>
      <p style={{ background: "rgba(8,97,206,0.06)", border: "1px solid rgba(8,97,206,0.25)", padding: "8px 14px", borderRadius: 6, fontSize: 12, margin: "0 0 18px", color: "var(--fg1)" }}>
        • Templates cascade: the Type-specific row wins → the built-in default for that stage renders otherwise. Variables use <code>{`{{ variable_name }}`}</code> syntax. Click a variable in the palette to insert it at the cursor.
      </p>
      <div className="set-emailbuilder">
        <div className="set-pane" style={{ padding: 18 }}>
          <h4 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 700 }}>Email Templates (per Type × Stage)</h4>
          <p style={{ fontSize: 12, color: "var(--fg2)", margin: "0 0 14px" }}>Each stage sends an email to the person assigned for that stage. Customise the template per Type when you need different wording for different rounds.</p>
          <div className="set-stage-tabs">
            {stages.map((s) => (
              <button key={s.id} className={`set-stage-tab ${stage === s.id ? "is-active" : ""}`} onClick={() => setStage(s.id)}>{s.label} <span className="set-stage-tab__default">DEFAULT</span></button>
            ))}
          </div>
          <div className="set-emailbuilder__field">
            <div className="set-eyebrow" style={{ marginBottom: 6 }}>SUBJECT</div>
            <input className="set-input set-input--full" value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <div className="set-emailbuilder__field">
            <div className="set-eyebrow" style={{ marginBottom: 6 }}>HTML BODY</div>
            <textarea className="set-input set-input--full set-input--mono" rows={18} value={body} onChange={(e) => setBody(e.target.value)} />
          </div>
          <div className="set-emailbuilder__field">
            <div className="set-eyebrow" style={{ marginBottom: 6 }}>PLAIN TEXT (OPTIONAL) <span style={{ color: "var(--fg2)", marginLeft: 6, textTransform: "none", letterSpacing: 0, fontWeight: 500 }}>Auto-generated from HTML if left blank.</span></div>
            <textarea className="set-input set-input--full set-input--mono" rows={6} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn sugg-modal__submit" onClick={() => toast.push("Saved for this Type",{tone:"ok"})}>Save for this Type</button>
              <button className="btn btn--ghost btn--sm" onClick={() => { setSubject(DEFAULTS[stage].subject); setBody(DEFAULTS[stage].body); toast.push("Reverted to default"); }}>Revert to default</button>
              <button className="btn btn--ghost btn--sm" onClick={wired.testEmail}>Send test to my email</button>
            </div>
            <span style={{ fontSize: 11, color: "var(--fg2)" }}>Source: <strong style={{ color: "var(--fg1)" }}>Default</strong></span>
          </div>
        </div>
        <div className="set-pane" style={{ padding: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>PREVIEW</h4>
            <select className="set-input set-input--sm"><option>sample data (today's date)</option></select>
          </div>
          <div style={{ background: "var(--surface-bg)", padding: "10px 14px", border: "1px solid var(--border-subtle)", borderRadius: 6, marginBottom: 10, fontSize: 12 }}>
            <strong>Subject:</strong> {subject.replace("{{ session_code }}", "041526_JepsenGrant")}
          </div>
          <div style={{ background: "#fff", border: "1px solid var(--border-subtle)", borderRadius: 6, padding: 0, fontSize: 13, lineHeight: 1.6, overflow: "hidden" }}>
            <div style={{ background: "var(--color-navy)", color: "#fff", padding: "20px 28px" }}>
              <div style={{ fontSize: 11, letterSpacing: ".18em", textTransform: "uppercase", color: "#B1C9E8" }}>VIN Transcript Software</div>
              <div style={{ fontSize: 18, fontWeight: 800, marginTop: 4 }}>{subject.replace("[VIN] ", "").replace("{{ session_code }}", "041526_JepsenGrant")}</div>
            </div>
            <div style={{ background: "var(--surface-bg)", padding: "16px 28px", fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--fg2)", lineHeight: 1.7, borderBottom: "1px solid var(--border-subtle)" }}>
              Uploaded May 17, 2026 · 120 segments · 18 slides · 4 speakers
            </div>
            <div style={{ padding: "20px 28px", color: "var(--fg1)" }}>
              <p style={{ margin: "0 0 10px" }}>Hi Lacy,</p>
              <p style={{ margin: "0 0 14px" }}>A new session has been uploaded and is ready for your prep review. Before copy edit can begin, please verify the extras and confirm everything needed is present.</p>
              <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: ".12em", textTransform: "uppercase", color: "var(--fg2)", margin: "14px 0 6px" }}>WHAT TO DO</div>
              <ol style={{ margin: "0 0 14px", paddingLeft: 22, fontSize: 13 }}>
                <li>Open the session and verify slides, chat, and polls are all present.</li>
                <li>Confirm the session code and title are correct.</li>
                <li>Flag any missing extras or malformed input.</li>
                <li>When ready, mark <strong>Prep complete</strong> to hand off to copy edit.</li>
              </ol>
              <button className="btn" style={{ background: "var(--color-navy)", color: "#fff" }}>Open session →</button>
            </div>
            <div style={{ padding: "12px 28px", background: "var(--surface-muted)", fontSize: 11, color: "var(--fg2)", borderTop: "1px solid var(--border-subtle)" }}>
              Sent by VIN Transcript Software · Reply to this email with questions
            </div>
          </div>
          <div style={{ marginTop: 18 }}>
            <div className="set-eyebrow" style={{ marginBottom: 8 }}>VARIABLES <span style={{ color: "var(--fg2)", marginLeft: 6, textTransform: "none", letterSpacing: 0, fontWeight: 500 }}>click to insert</span></div>
            {varCategories.map((cat) => (
              <div key={cat.name} style={{ marginBottom: 10 }}>
                <div className="set-eyebrow" style={{ fontSize: 9, marginBottom: 4 }}>{cat.name}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {cat.vars.map((v) => <code key={v} className="set-var-chip" onClick={() => insertVar(v)}>{v}</code>)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function SectionDiagnostics() {
  const [view, setView] = useState("home");
  if (view === "test") return <EmailDebug onBack={() => setView("home")} />;
  if (view === "gcs")  return <GCSDebug onBack={() => setView("home")} />;
  return (
    <>
      <SettingsHeader title="Diagnostics" lead="System health, observability counters, and operational probes." />
      <div className="set-card-block">
        <div className="set-eyebrow">TELEMETRY · §20 OBSERVABILITY</div>
        <h4 style={{ margin: "6px 0 6px", fontSize: 16, fontWeight: 700 }}>Phase 0 counters</h4>
        <p style={{ fontSize: 13, color: "var(--fg2)", lineHeight: 1.6, margin: "0 0 12px" }}>
          Live values: <code>longtasks/min: 1</code> · <code>heap: 108 MB · flat over 30m</code> · <code>WS RTT: 18ms</code> · <code>autosave: 2s ago</code>. All seven §20 modules operational.
        </p>
        <button className="btn btn--tertiary" onClick={() => setView("test")}>Open test email page →</button>
      </div>
      <div className="set-card-block">
        <div className="set-eyebrow">GCS · PIPELINE QA</div>
        <h4 style={{ margin: "6px 0 6px", fontSize: 16, fontWeight: 700 }}>G1–G14 pipeline checks</h4>
        <p style={{ fontSize: 13, color: "var(--fg2)", lineHeight: 1.6, margin: 0 }}>14 GCS-side checks running on a 5-minute cadence. 7-day uptime <strong>99.98%</strong>. Failing G13 (PII redaction sentinel) auto-rotating salt.</p>
        <button className="btn btn--tertiary" style={{ marginTop: 8 }} onClick={() => setView("gcs")}>Open GCS QA →</button>
      </div>
    </>
  );
}

function GCSDebug({ onBack }) {
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
    <>
      <div className="set-subnav">
        <button className="set-link" onClick={onBack}>← Settings</button>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>GCS Pipeline QA</h2>
        <span style={{ fontSize: 11, color: "var(--fg2)", marginLeft: 8 }}>14 checks · 5-minute cadence · streams to audit ledger</span>
      </div>
      <p style={{ background: "rgba(8,97,206,0.06)", border: "1px solid rgba(8,97,206,0.25)", padding: "10px 14px", borderRadius: 6, fontSize: 12, color: "var(--fg1)", margin: "0 0 18px" }}>
        • 14 checks across the GCS-side ingestion plane. Each check runs on a 5-minute cadence; results stream into the audit ledger. Failures trigger PagerDuty after two consecutive misses.
      </p>
      <div className="kpi-row" style={{ marginBottom: 18 }}>
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
    </>
  );
}

function EmailDebug({ onBack }) {
  return (
    <>
      <div className="set-subnav">
        <button className="set-link" onClick={onBack}>← Settings</button>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Test Email · Diagnostics</h2>
        <span style={{ fontSize: 11, color: "var(--fg2)", marginLeft: 8 }}>SMTP config · connectivity check · test send · copy-ready diagnostic bundle</span>
      </div>
      <p style={{ background: "rgba(8,97,206,0.06)", border: "1px solid rgba(8,97,206,0.25)", padding: "10px 14px", borderRadius: 6, fontSize: 12, color: "var(--fg1)", margin: "0 0 18px" }}>
        • Use this page to debug email send issues before contacting support. All three sections run against the same SMTP config as production stage notifications — failures reproduce exactly what a real send would do.
      </p>

      <div className="set-pane" style={{ padding: 18, marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>1. SMTP Config</h4>
          <button className="set-link" onClick={() => toast.push("Refreshed",{tone:"ok"})}>Refresh</button>
        </div>
        {[
          ["SMTP_HOST", "smtp.resend.com"],
          ["SMTP_PORT", "587"],
          ["SMTP_FROM", "mic@design.veterinary.support"],
          ["SMTP_USERNAME", "present"],
          ["SMTP_PASSWORD", "present"],
        ].map(([k, v]) => (
          <div key={k} className="set-smtp-row">
            <code>{k}</code>
            <span style={{ color: "var(--color-green)" }}>✓ <span style={{ color: v === "present" ? "var(--fg2)" : "var(--fg1)", fontStyle: v === "present" ? "italic" : "normal", marginLeft: 8 }}>{v}</span></span>
          </div>
        ))}
      </div>

      <div className="set-pane" style={{ padding: 18, marginBottom: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>2. Connectivity Test</h4>
          <button className="btn sugg-modal__submit" onClick={() => toast.push("SMTP connection OK",{tone:"ok"})}>Test SMTP Connection</button>
        </div>
        <div style={{ fontSize: 12, color: "var(--fg2)", marginTop: 10 }}>Not yet run.</div>
      </div>

      <div className="set-pane" style={{ padding: 18, marginBottom: 14 }}>
        <h4 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>3. Send Test Email</h4>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
          <FormRow label="TYPE"><select className="set-input"><option>default (global)</option>{SESSION_TYPES.slice(1).map((t) => <option key={t}>{t}</option>)}</select></FormRow>
          <FormRow label="STAGE"><select className="set-input">{SOP_STAGE_KEYS.map((s) => <option key={s.id}>{s.label.toUpperCase()}</option>)}</select></FormRow>
        </div>
        <FormRow label="SESSION (REAL DATA)"><select className="set-input"><option>— sample data (today's date) —</option>{MIC_DATA.SESSIONS.map((s) => <option key={s.id}>{s.code || s.id}</option>)}</select></FormRow>
        <FormRow label="To"><input className="set-input" defaultValue="johndean@vin.com" /></FormRow>
        <FormRow label="Subject"><input className="set-input" defaultValue="VIN Test Email" /></FormRow>
        <FormRow label="Body (plain text OR HTML — pasted template is rendered HTML)"><textarea className="set-input" rows={4} defaultValue="This is a test." /></FormRow>
        <div style={{ textAlign: "right" }}>
          <button className="btn sugg-modal__submit" onClick={wired.testEmail}>Send</button>
        </div>
      </div>

      <div style={{ background: "rgba(8,97,206,0.05)", border: "1px solid rgba(8,97,206,0.2)", padding: 12, borderRadius: 6, display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <button className="btn btn--tertiary" onClick={() => toast.push("Diagnostic bundle copied",{tone:"ok"})}>📋 Copy diagnostic bundle</button>
        <span style={{ fontSize: 12, color: "var(--fg2)" }}>Paste into a support ticket or share with your VIN admin. Never includes SMTP_USERNAME or SMTP_PASSWORD values.</span>
      </div>

      <div className="set-pane" style={{ padding: 18, marginBottom: 14 }}>
        <h4 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>4. Recent Attempts</h4>
        <table className="set-attempts">
          <thead><tr><th>WHEN</th><th>TRIGGER</th><th>TO</th><th>SUBJECT</th><th>RESULT</th><th>MS</th><th></th></tr></thead>
          <tbody>
            <tr><td>04/20/2026, 05:12:07 PM</td><td><code>debug_test</code></td><td>johndean.bali@gmail.com</td><td>[VIN] Ready to copy edit — 040126_Freema…</td><td style={{ color: "var(--color-green)" }}>✓ sent</td><td>1028</td><td><button className="btn btn--secondary btn--sm">Retest</button></td></tr>
            <tr><td>04/20/2026, 04:17:17 PM</td><td><code>debug_test</code></td><td>johndean.bali@gmail.com</td><td>VIN Test Email from production</td><td style={{ color: "var(--color-green)" }}>✓ sent</td><td>1057</td><td><button className="btn btn--secondary btn--sm">Retest</button></td></tr>
          </tbody>
        </table>
      </div>

      <div className="set-pane" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
          <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>5. Event Log</h4>
          <button className="set-link" onClick={() => toast.push("Cleared",{tone:"ok"})}>Clear</button>
        </div>
        <pre style={{ background: "#0B1626", color: "#DDE5ED", fontFamily: "var(--font-mono)", fontSize: 11, lineHeight: 1.6, padding: 14, borderRadius: 4, margin: 0, overflowX: "auto" }}>
{`08:10:53.028  INFO   email-debug page mounted
08:10:53.028  INFO   operator: johndean@vin.com
08:10:53.028  STEP   GET /v1/admin/email-debug/config
08:10:53.028  STEP   GET /v1/admin/email-debug/attempts?limit=50
08:10:53.028  STEP   GET /v1/sop/types
08:10:53.028  STEP   GET /v1/sessions?limit=50
08:10:53.451  OK     config loaded — present: host, port, from_address, username, password
08:10:53.459  OK     loaded 17 type(s)
08:10:53.475  OK     loaded 2 attempt(s)
08:10:53.497  OK     loaded 38 session(s) for picker`}</pre>
      </div>
    </>
  );
}

function SectionDeleted() {
  const items = [
    { code: "050226_Cheng",       title: "Equine Neonatal Resuscitation",                          deletedAt: "2026-05-15", by: "Kate Schultz" },
    { code: "042026_Ramirez",     title: "Avian Pediatric Wellness — A Hands-on Approach",          deletedAt: "2026-04-28", by: "Mendez M." },
    { code: "041226_Forsythe-v1", title: "Reproductive Imaging in the Bitch (v1 draft)",            deletedAt: "2026-04-20", by: "Kate Schultz" },
  ];
  return (
    <>
      <SettingsHeader title="Deleted sessions" lead="Soft-deleted sessions are recoverable for 30 days. After that, only the append-only ledger entries persist." />
      <div className="set-pane" style={{ padding: 0 }}>
        <div className="set-pane__head"><span className="set-eyebrow">RECOVERY · 30-DAY WINDOW · {items.length} sessions</span></div>
        {items.map((it, i) => (
          <div key={i} className="set-row">
            <div>
              <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 13, color: "var(--fg1)" }}>{it.code}</div>
              <div className="set-row__sub">{it.title}</div>
              <div style={{ fontSize: 11, color: "var(--fg2)", marginTop: 2 }}>Deleted {it.deletedAt} by {it.by} · {Math.floor((Date.now() - new Date(it.deletedAt).getTime()) / 86400000)}/30 days elapsed</div>
            </div>
            <div className="set-row__actions">
              <button className="btn btn--secondary btn--sm" onClick={async () => { const ok = await confirm.open({title:`Restore ${it.code}?`,confirmLabel:"Restore"}); if(!ok) return; auditLog.log("You","restore",`Restored ${it.code}`); toast.push(`${it.code} restored`,{tone:"ok"}); }}>Restore</button>
              <button className="set-link set-link--danger" onClick={async () => { const ok = await confirm.open({title:"Purge permanently?",body:"This cannot be undone. The audit-ledger entries persist.",danger:true,confirmLabel:"Purge"}); if(!ok) return; toast.push("Purged permanently",{tone:"attn"}); }}>Purge now</button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ── Helpers ───────────────────────────────────────────────
function SettingsHeader({ title, lead, headerCta }) {
  return (
    <div className="settings-row">
      <div>
        <h3>{title}</h3>
        <p>{lead}</p>
      </div>
      {headerCta ? <button className="btn btn--tertiary" onClick={headerCta.onClick}>{headerCta.label}</button> : null}
    </div>
  );
}
function FormRow({ label, sub, control, children }) {
  return (
    <div className="set-formrow">
      <div className="set-formrow__lbl">
        <div className="set-formrow__label">{label}</div>
        {sub ? <div className="set-formrow__sub">{sub}</div> : null}
      </div>
      <div className="set-formrow__ctrl">{control || children}</div>
    </div>
  );
}
function TogglePill({ on, onChange }) {
  return (
    <button className={`set-toggle ${on ? "is-on" : ""}`} onClick={() => onChange(!on)} aria-pressed={on}>
      <span className="set-toggle__knob" />
    </button>
  );
}

// ── Master router ─────────────────────────────────────────
function SettingsRouterPane({ active }) {
  switch (active) {
    case "general":     return <SectionGeneral />;
    case "team":        return <SectionTeam />;
    case "types":       return <SectionTypes />;
    case "ai-models":   return <SectionAIModels />;
    case "upload":      return <SectionUpload />;
    case "discrepancy": return <SectionDiscrepancy />;
    case "export":      return <SectionExport />;
    case "prompts":     return <SectionPromptTemplates />;
    case "manifest":    return <SectionManifest />;
    case "email":       return <SectionEmail />;
    case "diagnostics": return <SectionDiagnostics />;
    case "deleted":     return <SectionDeleted />;
    default:            return <SectionGeneral />;
  }
}

window.SettingsRouterPane = SettingsRouterPane;
