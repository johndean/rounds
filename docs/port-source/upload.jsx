/* eslint-disable no-undef */
// Upload route — /upload  (media intake)
// Dashboard route — /dashboard (operator overview)

function UploadRoute() {
  const [filesAttached, setFilesAttached] = useState(true);
  const [pipeline, setPipeline] = useState("direct");
  const [aiMode, setAiMode] = useState("transcript");
  const [model, setModel] = useState("gemini-25-pro");
  const [style, setStyle] = useState("lecture");
  const [styleOpen, setStyleOpen] = useState(true);
  const [iilOpen, setIilOpen] = useState(true);
  const [iilEnabled, setIilEnabled] = useState(true);
  const [tier1, setTier1] = useState(true);
  const [tier2, setTier2] = useState(true);
  const [tier3, setTier3] = useState(true);
  const [stt, setStt] = useState("google_latest_long");
  const [savedTpl, setSavedTpl] = useState("");

  const attached = [
    { kind: "AI Transcription",      file: "042326_Hendershott_audio.mp3",  size: "69.2 MB",  chip: "blue",  icon: "speaker" },
    { kind: "Video Playback",        file: "042326_Hendershott_vid.mp4",    size: "235.9 MB", chip: "blue",  icon: "play" },
    { kind: "Slide Extraction",      file: "042326_Hendershott.pdf",        size: "5.4 MB",   chip: "amber", icon: "slide" },
    { kind: "Chat Transcript",       file: "042326_Hendershott_chat.txt",   size: "16.1 KB",  chip: "blue",  icon: "message" },
    { kind: "Session Manifest",      file: "042326_Hendershott_extras2.txt", size: "12.5 KB",  chip: "blue",  icon: "doc" },
  ];

  // Processing-mode options (matches production)
  const aiModeOptions = [
    { value: "transcript",       label: "Transcript",       help: "Clean, enhanced transcript with corrected speech errors" },
    { value: "summary",          label: "Summary",          help: "Condensed summary of the session" },
    { value: "key-moments",      label: "Key Moments",      help: "Extracts the highest-signal moments from the session" },
    { value: "structured-notes", label: "Structured Notes", help: "Outline-style notes with sections and bullets" },
    { value: "custom-prompt",    label: "Custom Prompt",    help: "User-defined processing instructions" },
  ];

  // Processing-style catalog (matches production categories)
  const styleCategories = [
    { id: "education", label: "Education", items: [
      { id: "lecture",  name: "Lecture",            icon: "🎓", desc: "Optimized for structured teaching content" },
      { id: "training", name: "Training / Workshop", icon: "🛠️", desc: "Handles Q&A, exercises and interaction patterns" },
    ]},
    { id: "technical", label: "Technical", items: [
      { id: "technical", name: "Technical Deep Dive", icon: "⚙️", desc: "Terminology preservation — minimal rewrite" },
    ]},
    { id: "conversational", label: "Conversational", items: [
      { id: "podcast", name: "Podcast / Conversation", icon: "🎙️", desc: "Light cleanup — conversational flow preserved" },
    ]},
    { id: "business", label: "Business", items: [
      { id: "sales", name: "Sales / Presentation", icon: "📊", desc: "Emphasis and persuasion patterns preserved" },
    ]},
    { id: "ai-prompt", label: "AI Prompt", items: [
      { id: "transcript-prompt", name: "Transcript", icon: "📝", desc: "Clean, enhanced transcript with corrected speech errors" },
    ]},
    { id: "custom", label: "Custom", items: [
      { id: "custom-define", name: "Custom",                  icon: "⚡", desc: "Define your own processing rules" },
      { id: "transcript-pv1", name: "Transcript (Paragraph v1)", icon: "📝", desc: "Clean, enhanced transcript with corrected speech errors" },
    ]},
  ];
  const allStyles = styleCategories.flatMap((c) => c.items);
  const currentStyle = allStyles.find((s) => s.id === style) || allStyles[0];

  // Style chips (the trait pills below the catalog)
  const styleChips = [
    { id: "filler",      label: "filler: strict",     emphasis: true },
    { id: "terms",       label: "terms: medium",      emphasis: false },
    { id: "structure",   label: "structure: on",      emphasis: true },
    { id: "key-points",  label: "key points: on",     emphasis: true },
    { id: "tone",        label: "tone: neutral",      emphasis: false },
  ];

  // IIL tiers (matches production)
  const tiers = [
    { id: "t1", label: "Tier 1 — Acoustic Fillers",   sub: "Removes hesitation sounds with no semantic meaning", chip: "red",    words: ["um", "uh", "er", "ah"],                                          on: tier1, set: setTier1 },
    { id: "t2", label: "Tier 2 — Discourse Fillers",  sub: "Removes conversational filler words only when meaning is preserved", chip: "amber", words: ["you know", "basically", "like", "right", "essentially"], on: tier2, set: setTier2 },
    { id: "t3", label: "Tier 3 — Redundant Phrases",  sub: "Shortens repetitive phrases without changing meaning",               chip: "teal",  words: ["what I'm saying is", "the thing is", "what we're going to do is"], on: tier3, set: setTier3 },
  ];

  // Saved prompt templates (used in Custom Prompt mode)
  const savedTemplates = [
    { group: "AI Prompt", items: [{ id: "ai-transcript", label: "Transcript" }] },
    { group: "Custom",    items: [{ id: "custom-pv1",    label: "Transcript (Paragraph v1)" }] },
  ];

  const isCustom = aiMode === "custom-prompt";
  const currentAiMode = aiModeOptions.find((o) => o.value === aiMode);

  return (
    <main className="upload-page" data-screen-label="Upload">
      <div style={{ maxWidth: 760, margin: "0 auto", padding: "44px 24px 64px" }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 11, fontWeight: 700, letterSpacing: ".14em", textTransform: "uppercase", color: "var(--fg-link)", marginBottom: 10 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--fg-link)" }} /> Media Intelligence Compiler
          </div>
          <h1 style={{ fontSize: 38, fontWeight: 800, lineHeight: 1.1, margin: "0 0 12px", color: "var(--fg1)", textWrap: "balance" }}>
            Turn lectures into<br />structured content
          </h1>
          <p style={{ fontSize: 14, color: "var(--fg2)", margin: 0, maxWidth: 480, marginInline: "auto" }}>
            Upload video. We produce a clean verbatim transcript aligned to every slide.
          </p>
        </div>

        {/* Drop zone */}
        <div className={`upload-dropzone ${filesAttached ? "is-active" : ""}`} onClick={() => setFilesAttached((v) => !v)}>
          {filesAttached ? (
            <>
              <div style={{ width: 56, height: 56, borderRadius: 14, background: "rgba(8,97,206,0.18)", display: "inline-flex", alignItems: "center", justifyContent: "center", marginBottom: 14 }}>
                <Icon name="doc" size={26} />
              </div>
              <div style={{ fontSize: 17, fontWeight: 700, color: "var(--fg1)" }}>5 files selected</div>
              <div style={{ fontSize: 13, color: "var(--fg-link)", marginTop: 4 }}>✓ Ready to process · click to add more</div>
            </>
          ) : (
            <>
              <div style={{ width: 56, height: 56, borderRadius: 14, background: "var(--surface-muted)", display: "inline-flex", alignItems: "center", justifyContent: "center", marginBottom: 14 }}>
                <Icon name="download" size={26} className="upload-dropzone__arrow" />
              </div>
              <div style={{ fontSize: 17, fontWeight: 700, color: "var(--fg1)" }}>Drop your files here</div>
              <div style={{ fontSize: 12, color: "var(--fg2)", marginTop: 4 }}>Video, audio, PDF, PPTX, text · multiple files supported</div>
            </>
          )}
        </div>

        {filesAttached ? (
          <>
            <div className="upload-attach-note">
              AI will process: <strong>{attached[0].file}</strong> + <strong>{attached[2].file}</strong> together · <strong>{attached[1].file}</strong> for playback
            </div>
            {attached.map((a) => (
              <div key={a.kind}>
                <div className="upload-attach-label">
                  {a.kind}
                  {a.kind === "Session Manifest" ? <span style={{ marginLeft: 6, fontWeight: 600, color: "var(--fg2)", textTransform: "none", letterSpacing: 0 }}>(extras2) — populates speaker labels, per-slide resources, and publishing links</span> : null}
                </div>
                <div className="upload-attach">
                  <Icon name={a.icon} size={16} />
                  <span className="upload-attach__name">{a.file}</span>
                  <span className="upload-attach__size">{a.size}</span>
                  <span className={`chip chip--${a.chip}`} style={{ fontSize: 10, padding: "3px 9px" }}>{a.kind}</span>
                  <button className="btn btn--ghost btn--icon btn--sm" data-test-id={`upload-remove-${a.kind.replace(/\s/g, "")}`} title="Remove" onClick={() => wired.toastInfo(`Removed ${a.file}`, "attn")}><Icon name="x" size={11} /></button>
                </div>
              </div>
            ))}
          </>
        ) : null}

        {/* Form sections */}
        <div className="upload-form">
          {/* Processing Pipeline */}
          <div className="upload-field">
            <label className="upload-field__label" style={{ color: "var(--color-amber)" }}>
              <Icon name="lightning" size={12} /> Processing Pipeline
            </label>
            <select className="upload-field__select" value={pipeline} onChange={(e) => setPipeline(e.target.value)}>
              <option value="direct">Direct to AI — file sent directly to Gemini</option>
              <option value="enhanced">AI-Enhanced — transcribe first, then AI refines</option>
            </select>
            <div className="upload-field__help">
              {pipeline === "direct"
                ? "Gemini processes the media file directly and returns a formatted transcript"
                : "Google STT generates word-level timing; Gemini reconciles to clean prose"}
            </div>
          </div>

          {/* AI Processing Mode */}
          <div className="upload-field">
            <label className="upload-field__label" style={{ color: "var(--color-blue)" }}>
              <Icon name="users" size={12} /> Select AI Processing Mode
            </label>
            <select className="upload-field__select" value={aiMode} onChange={(e) => setAiMode(e.target.value)}>
              {aiModeOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <div className="upload-field__help">{currentAiMode?.help}</div>
          </div>

          {/* AI Model */}
          <div className="upload-field">
            <label className="upload-field__label" style={{ color: "#C5478D" }}>
              <Icon name="globe" size={12} /> AI Model
            </label>
            <select className="upload-field__select" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="gemini-25-pro">Gemini 2.5 Pro (recommended)</option>
              <option value="gemini-25-flash">Gemini 2.5 Flash (faster, lower quality)</option>
              <option value="gpt-5">GPT-5</option>
              <option value="claude-opus">Claude Opus 4.5</option>
            </select>
          </div>

          {/* Custom Prompt mode: saved template loader + textarea */}
          {isCustom ? (
            <>
              <div className="upload-field">
                <label className="upload-field__label" style={{ color: "var(--color-green)" }}>
                  <Icon name="save" size={12} /> Load Saved Prompt Template <span style={{ marginLeft: 8, fontSize: 9, color: "var(--fg2)", fontWeight: 600, padding: "2px 6px", background: "var(--surface-muted)", borderRadius: 4, textTransform: "none", letterSpacing: 0 }}>optional</span>
                </label>
                <select className="upload-field__select" value={savedTpl} onChange={(e) => setSavedTpl(e.target.value)} style={savedTpl ? { borderColor: "var(--color-green)", boxShadow: "0 0 0 2px rgba(0,125,97,0.10)" } : null}>
                  <option value="">— pick a saved template to load below —</option>
                  {savedTemplates.map((g) => (
                    <optgroup key={g.group} label={g.group}>
                      {g.items.map((it) => <option key={it.id} value={it.id}>{it.label}</option>)}
                    </optgroup>
                  ))}
                </select>
                <div className="upload-field__help">Loads the saved prompt into the textarea below. Edit freely after loading.</div>
              </div>
              <div className="upload-field">
                <label className="upload-field__label" style={{ color: "var(--color-blue)" }}>
                  <Icon name="edit" size={12} /> Custom Prompt
                </label>
                <textarea
                  className="upload-field__select"
                  rows={10}
                  style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, lineHeight: 1.55, padding: "12px 14px", resize: "vertical" }}
                  defaultValue={`You are generating a MIC transcript that must be 100% compliant with the
full Transcript SOP and downstream processing pipeline.

This transcript will flow through:
- Medical Review
- Copy Edit Review
- CMS Publishing
- Captions on Video
- QA

Verbatim-minus-fillers · preserve drug names · annotate uncertainty.`}
                />
              </div>
            </>
          ) : null}

          {/* STT (only when AI-Enhanced) */}
          <div className={`upload-field ${pipeline !== "enhanced" ? "upload-field--disabled" : ""}`}>
            <label className="upload-field__label">
              <Icon name="speaker" size={12} /> Speech-to-Text (STT)
              <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--fg2)", textTransform: "none", letterSpacing: 0, fontWeight: 500 }}>
                Applied when Processing Pipeline = AI-Enhanced
              </span>
            </label>
            <select className="upload-field__select" value={stt} onChange={(e) => setStt(e.target.value)} disabled={pipeline !== "enhanced"}>
              <option value="google_latest_long">Google STT v3 · latest_long</option>
              <option value="google_phone">Google STT · phone_call</option>
            </select>
          </div>

          {/* Processing Style — expanded card */}
          <div className="upload-style-card">
            <div className="upload-style-card__head">
              <label className="upload-field__label" style={{ color: "var(--fg2)", marginBottom: 0 }}>
                <Icon name="settings" size={12} /> Processing Style
                <span className="chip chip--ghost" style={{ marginLeft: 8, fontSize: 9 }}>v3.10</span>
              </label>
              <button className="btn btn--ghost btn--icon btn--sm" onClick={() => setStyleOpen((v) => !v)} aria-expanded={styleOpen}>
                <Icon name={styleOpen ? "chevron-down" : "chevron-right"} size={14} style={{ transform: styleOpen ? "rotate(0deg)" : "rotate(0deg)" }} />
              </button>
            </div>
            <button className="upload-style-current" onClick={() => setStyleOpen((v) => !v)}>
              <span style={{ fontSize: 22 }}>{currentStyle.icon}</span>
              <span>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--fg1)" }}>{currentStyle.name}</div>
                <div style={{ fontSize: 12, color: "var(--fg2)", marginTop: 1 }}>{currentStyle.desc}</div>
              </span>
              <Icon name={styleOpen ? "chevron-down" : "chevron-right"} size={14} style={{ marginLeft: "auto", color: "var(--fg2)" }} />
            </button>

            {styleOpen ? (
              <div className="upload-style-list">
                {styleCategories.map((cat) => (
                  <div key={cat.id}>
                    <div className="upload-style-cat">{cat.label}</div>
                    {cat.items.map((it) => {
                      const isSel = it.id === style;
                      return (
                        <button key={it.id} className={`upload-style-item ${isSel ? "is-selected" : ""}`} onClick={() => setStyle(it.id)}>
                          <span style={{ fontSize: 18 }}>{it.icon}</span>
                          <span>
                            <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--fg1)" }}>{it.name}</div>
                            <div style={{ fontSize: 11.5, color: "var(--fg2)" }}>{it.desc}</div>
                          </span>
                          {isSel ? <Icon name="check" size={14} className="upload-style-item__chk" /> : null}
                        </button>
                      );
                    })}
                  </div>
                ))}

                <div className="upload-style-chips">
                  {styleChips.map((c) => (
                    <span key={c.id} className={`upload-style-chip ${c.emphasis ? "is-emphasis" : ""}`}>{c.label}</span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          {/* Instructor Intelligence Layer — expanded view */}
          <div className={`upload-iil-card ${iilOpen ? "is-open" : ""}`}>
            <div className="upload-iil-card__head">
              <button className="upload-iil-card__title" onClick={() => setIilOpen((v) => !v)}>
                <span style={{ fontSize: 22 }}>🧠</span>
                <span>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--color-blue)" }}>Instructor Intelligence Layer</div>
                  <div style={{ fontSize: 11, color: "var(--fg2)", marginTop: 2 }}>{iilOpen ? "Click to collapse" : "Click to expand"} · configure tier rules {iilOpen ? "below" : ""}</div>
                </span>
                <Icon name={iilOpen ? "chevron-down" : "chevron-right"} size={14} style={{ marginLeft: "auto", color: "var(--fg2)" }} />
              </button>
              <button className="upload-iil__toggle" onClick={(e) => { e.stopPropagation(); setIilEnabled((v) => !v); }} aria-pressed={iilEnabled} title="Toggle IIL">
                <span className={`upload-iil__knob ${iilEnabled ? "is-on" : ""}`} />
              </button>
            </div>
            {iilOpen ? (
              <div className="upload-iil-tiers">
                {tiers.map((t) => (
                  <div key={t.id} className="upload-iil-tier">
                    <div className="upload-iil-tier__head">
                      <div>
                        <div className={`upload-iil-tier__label upload-iil-tier__label--${t.chip}`}>{t.label}</div>
                        <div className="upload-iil-tier__sub">{t.sub}</div>
                      </div>
                      <button className="upload-iil__toggle" onClick={() => t.set(!t.on)} aria-pressed={t.on}>
                        <span className={`upload-iil__knob ${t.on ? "is-on" : ""}`} />
                      </button>
                    </div>
                    <div className="upload-iil-words">
                      {t.words.map((w) => (
                        <span key={w} className={`upload-iil-word upload-iil-word--${t.chip}`}>{w}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <button className="btn btn--primary upload-process" data-test-id="upload-process" onClick={async () => {
            if (!filesAttached) { wired.toastInfo("Add at least one file", "attn"); return; }
            wired.toastInfo("Starting processing…");
            await api.uploadFile("batch", "5 files");
            auditLog.log("You", "upload", "Submitted 5 files for processing");
            navigate("/p/se_007");
          }}>
            Process &nbsp;→
          </button>
          <p style={{ textAlign: "center", fontSize: 11, color: "var(--fg2)", marginTop: 10 }}>
            Processing may take longer depending on file size
          </p>
        </div>
      </div>
    </main>
  );
}

window.UploadRoute = UploadRoute;
