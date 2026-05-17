/* eslint-disable no-undef */
// Viewer (Preview) route — /v/:id
// Export-preview document. Read-only, print-ready, shows every artifact a
// reviewer needs to verify before publishing: identity header, downloadable
// format cards, publishing checklist with links, and per-slide transcript
// preview rendered exactly as it would appear in the final export.

function ViewerRoute({ id }) {
  const session = MIC_DATA.SESSIONS.find((s) => s.id === id) || MIC_DATA.SESSIONS[0];
  const segments = MIC_DATA.SEGMENTS;
  const slides = MIC_DATA.SLIDES;
  const segmentsBySlide = useMemo(() => {
    const m = new Map();
    slides.forEach((sl) => m.set(sl.id, []));
    segments.forEach((s) => { if (s.slide_id) m.get(s.slide_id)?.push(s); });
    return m;
  }, [segments, slides]);

  const [includeKeyPoints, setIncludeKeyPoints] = useState(false);

  const downloads = [
    { kind: "Word Document",  ext: ".docx", desc: "Macro-compatible transcript with slide codes and speaker labels. Run SRT_Transcript or CMS_Transcript macro to prep for publishing." },
    { kind: "Captions",       ext: ".srt",  desc: "SubRip subtitle file for Wistia or video player caption upload." },
    { kind: "Plain Text",     ext: ".txt",  desc: "Simple text for email, forum paste, or quick reference." },
    { kind: "Word Macro",     ext: ".zip",  desc: "One-time install. Open in Word, Developer, Visual Basic, Import." },
  ];

  const publishing = [
    { label: "Zoom recording",  href: "https://vin.zoom.us/s/94555598059" },
    { label: "Slides",          href: "https://www.vin.com/members/slideshow/SlideShowData.ashx?ProjectId=35411" },
    { label: "Podbean",         href: "https://vincasts.podbean.com/e/wildlife-conservation-translocations-how-zoos-make-decisions-reduce-risk/" },
    { label: "VINcast",         href: "https://www.vin.com/doc/?id=13096848" },
    { label: "Intranet",        href: "https://www.vin.com/Admin/Intranet/Client.plx?UniqueID=209370" },
    { label: "Message board",   href: "https://www.vin.com/doc/?Id=13088616&SAId=2&IsMBLink=1&MyActivities=1" },
    { label: "Session page",    href: "https://www.vin.com/doc/?id=12943766" },
  ];

  // Build the per-slide rendered transcript: one slide section = one card with
  // the slide title + any speaker bio/objectives + every segment for that slide.
  return (
    <main className="preview-page" data-screen-label="Viewer / Preview">
      {/* Identity header */}
      <div className="preview-id">
        <div className="preview-id__code">{session.code || session.id}</div>
        <h1 className="preview-id__title">{session.title}</h1>
        <div className="preview-id__interim">INTERIM: {session.title.replace(/^.+?: /, "").slice(0, 80)}</div>
        <div className="preview-id__chips">
          <span className="chip chip--ghost"><strong style={{ fontWeight: 700 }}>CLASS ID</strong> VINR414-0126</span>
          <span className="chip chip--blue">Student</span>
          <span className="chip chip--blue">Veterinary</span>
        </div>
      </div>

      {/* Export Preview toolbar */}
      <div className="preview-toolbar">
        <div>
          <h2 className="preview-section-title">Export Preview</h2>
        </div>
        <div className="preview-toolbar__actions">
          <label className="preview-toolbar__check">
            <input type="checkbox" checked={includeKeyPoints} onChange={(e) => setIncludeKeyPoints(e.target.checked)} />
            Include key points section
          </label>
          <Link to={`/e/${session.id}`} className="btn btn--secondary"><Icon name="chevron-left" /> Editor</Link>
        </div>
      </div>

      {/* Format cards */}
      <div className="preview-formats">
        {downloads.map((d) => (
          <button key={d.ext} className="preview-format" data-test-id={`preview-${d.ext.slice(1)}`} onClick={() => wired.download(d.ext.slice(1), session.code || session.id)}>
            <div className="preview-format__head">
              <Icon name="download" size={13} />
              <span className="preview-format__kind">{d.kind}</span>
              <code className="preview-format__ext">{d.ext}</code>
            </div>
            <div className="preview-format__desc">{d.desc}</div>
          </button>
        ))}
      </div>

      {/* Publishing checklist */}
      <div className="preview-checklist">
        <div className="preview-checklist__head">PUBLISHING CHECKLIST</div>
        <div className="preview-checklist__body">
          {publishing.map((p) => (
            <div key={p.label} className="preview-checklist__row">
              <a href={p.href} className="preview-checklist__label" onClick={(e) => { e.preventDefault(); wired.toastInfo(`Open ${p.label} (mock)`); }}>{p.label}</a>
              <code className="preview-checklist__url">{p.href}</code>
            </div>
          ))}
        </div>
      </div>

      {/* Per-slide transcript preview cards */}
      <div className="preview-slides">
        {slides.map((sl) => {
          const segs = segmentsBySlide.get(sl.id) || [];
          if (!segs.length && sl.kind !== "title" && sl.kind !== "bio") return null;
          return (
            <article key={sl.id} className="preview-slide">
              <h3 className="preview-slide__title">Slide {sl.n}</h3>
              {sl.kind === "bio" || sl.kind === "objectives" || sl.kind === "title" ? (
                <div className="preview-slide__centered">{sl.title}</div>
              ) : null}
              <div className="preview-slide__body">
                {segs.length === 0 ? (
                  <div className="preview-slide__noaudio">( no audio )</div>
                ) : (
                  segs.map((seg) => {
                    const sp = MIC_DATA.SPEAKERS[seg.speaker];
                    return (
                      <p key={seg.id} className="preview-slide__para">
                        <strong>**{sp.short.replace(/^Dr\. /, "")}:**</strong> {seg.text}
                      </p>
                    );
                  })
                )}
              </div>
            </article>
          );
        })}
      </div>

      {includeKeyPoints ? (
        <div className="preview-keypoints">
          <h3 className="preview-section-title" style={{ marginBottom: 14 }}>Key Points</h3>
          <ul style={{ fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: 1.75, color: "var(--fg1)", paddingLeft: 20 }}>
            <li>GI foreign body removal is one of the most common soft-tissue surgeries; ~78% canine, ~19% feline incidence.</li>
            <li>Linear FBs are dangerous because of plication — never pull on a linear FB until proximally unanchored.</li>
            <li>Three-criterion resection rule: non-viability, perforation, or {">"}50% lumen compromise.</li>
            <li>Sublingual exam non-negotiable in every vomiting cat.</li>
            <li>Closure pattern doesn't statistically affect dehiscence rate (~2.8% vs 3.1%, p=0.64).</li>
          </ul>
        </div>
      ) : null}

      <div style={{ padding: "30px 0", textAlign: "center", fontSize: 11, color: "var(--fg2)", fontFamily: "var(--font-mono)" }}>
        End of preview · {segments.length} segments · {slides.length} slides · build v4.0.0-ssot-r2
      </div>
    </main>
  );
}

window.ViewerRoute = ViewerRoute;
