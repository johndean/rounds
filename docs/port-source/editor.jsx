/* eslint-disable no-undef */
// Editor route — /e/:id
// Composes: top bar, playback, tabs, slide rail (focus/filter), transcript, right rail.

// ── Slide Rail ─────────────────────────────────────────────
function SlideRail({ slides, activeSlideId, focusedSlideId, mode, onModeChange, onSlideClick, onClearFocus, segmentsBySlide }) {
  return (
    <div className="sliderail" aria-label="Slide rail" data-screen-label="Slide Rail">
      <div className="sliderail__head">
        <h4>Slides · {slides.length}</h4>
        <div className="sliderail__toggle" role="radiogroup" aria-label="Slide click mode">
          <button
            className={mode === "focus" ? "is-active" : ""}
            onClick={() => onModeChange("focus")}
            role="radio" aria-checked={mode === "focus"}
            title="Focus mode — click a slide to scroll to it; all segments stay visible">
            <Icon name="circle-dot" size={11} /> Focus
          </button>
          <button
            className={mode === "filter" ? "is-active" : ""}
            onClick={() => onModeChange("filter")}
            role="radio" aria-checked={mode === "filter"}
            title="Filter mode — click a slide to show only its segments (legacy)">
            <Icon name="filter" size={11} /> Filter
          </button>
        </div>
        {focusedSlideId ? (
          <button
            className="sliderail__clear"
            onClick={(e) => { e.stopPropagation(); onClearFocus && onClearFocus(); }}
            title={mode === "focus" ? "Clear focus" : "Show all"}>
            {mode === "focus" ? "Clear focus" : "Show all"}
          </button>
        ) : null}
      </div>
      <ul className="sliderail__list">
        {slides.map((sl) => {
          const segs = segmentsBySlide.get(sl.id) || [];
          const accent = slideAccent(sl.id);
          const isActive = sl.id === activeSlideId;
          const isFocused = sl.id === focusedSlideId;
          const isEmpty = segs.length === 0;
          const cls = ["slide-card"];
          if (isActive) cls.push("is-active");
          if (isFocused && mode === "focus") cls.push("is-focused-target");
          if (isEmpty) cls.push("is-empty");

          // 3-branch nav style (matches production slideMetaById)
          let inlineStyle;
          if (isActive) {
            inlineStyle = { background: withAlpha(accent, "22"), borderColor: accent, boxShadow: `inset 3px 0 0 ${accent}` };
          } else if (isEmpty) {
            inlineStyle = { opacity: 0.55, boxShadow: `inset 3px 0 0 ${withAlpha(accent, "33")}` };
          } else {
            inlineStyle = { background: withAlpha(accent, "12"), borderColor: withAlpha(accent, "44"), boxShadow: `inset 3px 0 0 ${accent}` };
          }
          return (
            <li key={sl.id}>
              <div className={cls.join(" ")} style={inlineStyle} onClick={() => onSlideClick(sl.id)} title={sl.title}>
                <div className="slide-card__thumb" style={{ background: `linear-gradient(160deg, ${accent} 0%, ${withAlpha(accent, "cc")} 100%)`, borderColor: accent }}>{String(sl.n).padStart(2, "0")}</div>
                <div className="slide-card__title">{sl.title.replace(/^(Title — |Case Study \d+ — )/, "")}</div>
                <span className="slide-card__count" style={isActive ? null : (segs.length ? { color: accent } : null)}>{segs.length}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── VideoStrip — sits at top of left column with compact audio controls ──
function VideoStrip({
  session, activeSlide, slides, time, total, playing, setPlaying,
  rate, setRate, cc, setCc, muted, setMuted, volume, setVolume,
  setTime, onScrubClick, segmentsBySlide,
}) {
  return (
    <div className="vstrip" data-screen-label="Video Player">
      <div className="vstrip__frame" onClick={() => setPlaying((p) => !p)} role="button" aria-label={playing ? "Pause video" : "Play video"}>
        <div className="vstrip__poster">
          <div className="vstrip__slide-no">{activeSlide ? activeSlide.title.split(" ")[0].toUpperCase() : "—"}</div>
          <div className="vstrip__slide-title">{activeSlide?.title || "—"}</div>
          <div className="vstrip__slide-meta">
            <span>{session.presenter?.replace(/^Dr\. /, "Dr. ")}</span>
            <span>VIN / NAVAS ROUNDS</span>
            <span>{session.recorded || "JANUARY 12, 2025"}</span>
          </div>
        </div>
        <div className="vstrip__scan" />
        {!playing ? (
          <div className="vstrip__overlay">
            <div className="vstrip__center-play"><Icon name="play" size={26} /></div>
          </div>
        ) : null}
        <div className="vstrip__hud">
          <span className="vstrip__hud-icons">
            <Icon name="skip-back"   size={11} /><Icon name="edit"  size={11} />
            <Icon name="search"      size={11} /><Icon name="slide" size={11} />
            <Icon name="more"        size={11} />
          </span>
          <span className="vstrip__timecode">{new Date().toISOString().slice(0,10).replace(/-/g,"-")} {fmtTime(time)} / {fmtTime(total)}</span>
        </div>
      </div>
      <div className="vstrip__bar">
        <button className="vstrip__play" onClick={() => setPlaying((p) => !p)} title={playing ? "Pause" : "Play"}>
          <Icon name={playing ? "pause" : "play"} size={12} />
        </button>
        <select className="vstrip__rate" value={rate} onChange={(e) => setRate(parseFloat(e.target.value))}>
          <option value="0.75">0.75×</option>
          <option value="1">1×</option>
          <option value="1.25">1.25×</option>
          <option value="1.5">1.5×</option>
          <option value="2">2×</option>
        </select>
        <button className={`vstrip__cc ${cc ? "is-on" : ""}`} onClick={() => setCc((v) => !v)} title="Captions">CC</button>
        <div className="vstrip__scrubber" onClick={onScrubClick} role="slider" aria-valuenow={time} aria-valuemin={0} aria-valuemax={total}>
          <div className="vstrip__track"><span style={{ width: `${(time / total) * 100}%` }} /></div>
          <div className="vstrip__chapter-marks">
            {slides.map((sl) => {
              const segs = segmentsBySlide.get(sl.id);
              if (!segs || !segs.length) return null;
              return <span key={sl.id} style={{ left: `${(segs[0].start / total) * 100}%` }} title={`Slide ${sl.n}`} />;
            })}
          </div>
          <div className="vstrip__head" style={{ left: `${(time / total) * 100}%` }} />
        </div>
        <span className="vstrip__time">{fmtTime(time).split(":").slice(-1)[0] === "00" ? `00:${String(Math.floor(time / 60)).padStart(2,"0")}` : fmtTime(time)}</span>
      </div>
    </div>
  );
}

// ── Right Rail (Active Slide + Admin/Chat/Polls) ───────────
function ActiveSlideCard({ slide, segmentCount, collapsed, onToggle, time, totalDuration }) {
  if (!slide) return null;
  const accent = slideAccent(slide.id);
  return (
    <div className={`rightrail__activeslide ${collapsed ? "is-collapsed" : ""}`} style={{ borderLeft: `4px solid ${accent}` }}>
      <div className="rightrail__activeslide-header" onClick={onToggle} role="button" aria-expanded={!collapsed}>
        <h4 style={{ color: accent }}>Active Slide</h4>
        <Icon name="chevron-down" size={14} className="chev" />
      </div>
      <div className="rightrail__activeslide-body">
        <div className="slide-preview" style={{ background: `linear-gradient(160deg, ${accent} 0%, ${withAlpha(accent, "cc")} 100%)`, backgroundImage: `radial-gradient(ellipse at 80% 50%, rgba(255,255,255,0.10) 0%, transparent 60%), repeating-linear-gradient(-45deg, rgba(255,255,255,0.05) 0, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 10px), linear-gradient(160deg, ${accent} 0%, ${withAlpha(accent, "cc")} 100%)` }}>
          <div className="slide-preview__no">Slide {String(slide.n).padStart(2, "0")} of {MIC_DATA.SLIDES.length}</div>
          <div className="slide-preview__title">{slide.title}</div>
          <div className="slide-preview__foot">
            <span>{slide.kind}</span>
            <span>{segmentCount} seg</span>
          </div>
        </div>
        <div className="minimap" aria-label="Session timeline minimap">
          <svg viewBox="0 0 200 20" preserveAspectRatio="none">
            {MIC_DATA.SLIDES.map((s) => {
              const segs = MIC_DATA.SEGMENTS.filter((g) => g.slide_id === s.id);
              if (!segs.length) return null;
              const x1 = (segs[0].start / totalDuration) * 200;
              const x2 = (segs[segs.length - 1].end / totalDuration) * 200;
              const isCurrent = s.id === slide.id;
              const fill = isCurrent ? slideAccent(s.id) : withAlpha(slideAccent(s.id), "55");
              return <rect key={s.id} x={x1} y={4} width={Math.max(1, x2 - x1)} height={12} fill={fill} stroke={isCurrent ? slideAccent(s.id) : "none"} strokeWidth={isCurrent ? 0.5 : 0} />;
            })}
          </svg>
          <div className="minimap__head" style={{ left: `${(time / totalDuration) * 100}%` }} />
        </div>
        <button className="btn btn--secondary btn--sm" style={{ width: "100%" }} onClick={() => wired.toastInfo("Slide reassignment picker (mock)")}>
          <Icon name="slide" size={12} /> Re-assign segments to slide
        </button>
      </div>
    </div>
  );
}

function AdminTab({ slide, segments, time, totalDuration, slides }) {
  if (!slide) return <div style={{ fontSize: 12, color: "var(--fg2)" }}>No active slide.</div>;
  const segs = segments.filter((s) => s.slide_id === slide.id);
  const accent = slideAccent(slide.id);
  return (
    <div>
      <div className="rightrail__sectionhead">Timeline · session map</div>
      <div className="minimap" aria-label="Session timeline minimap" style={{ marginBottom: 12 }}>
        <svg viewBox="0 0 200 20" preserveAspectRatio="none">
          {slides.map((s) => {
            const sSegs = segments.filter((g) => g.slide_id === s.id);
            if (!sSegs.length) return null;
            const x1 = (sSegs[0].start / totalDuration) * 200;
            const x2 = (sSegs[sSegs.length - 1].end / totalDuration) * 200;
            const isCurrent = s.id === slide.id;
            const fill = isCurrent ? slideAccent(s.id) : withAlpha(slideAccent(s.id), "55");
            return <rect key={s.id} x={x1} y={4} width={Math.max(1, x2 - x1)} height={12} fill={fill} stroke={isCurrent ? slideAccent(s.id) : "none"} strokeWidth={isCurrent ? 0.5 : 0} />;
          })}
        </svg>
        <div className="minimap__head" style={{ left: `${(time / totalDuration) * 100}%` }} />
      </div>

      <div className="rightrail__sectionhead">Segments on this slide · {segs.length}</div>
      <ul className="admin-segment-list">
        {segs.map((s) => {
          const isActive = time >= s.start && time < s.end + 0.25;
          return (
            <li key={s.id} style={{
              background: isActive ? withAlpha(accent, "33") : withAlpha(accent, "12"),
              borderLeftColor: accent,
              borderLeftWidth: isActive ? 3 : 2,
            }}>
              <span className="t" style={{ color: accent }}>{fmtTime(s.start)}</span>
              <span style={{ display: "-webkit-box", WebkitLineClamp: 1, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{s.text}</span>
            </li>
          );
        })}
      </ul>
      <div className="rightrail__sectionhead">Instructor</div>
      <div className="instructor-card">
        <div className="instructor-card__av">PM</div>
        <div>
          <div className="instructor-card__name">Dr. Pamela Mueller, DVM, DACVS</div>
          <div className="instructor-card__role">Soft Tissue Surgery · University of Wisconsin SVM</div>
          <div className="instructor-card__meta">23 sessions on VIN · avg 1.0h · 4.8 rating</div>
        </div>
      </div>
      <div className="rightrail__sectionhead">IIL signals (preview)</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 11 }}>
        <div style={{ padding: "6px 8px", background: "var(--surface-bg)", border: "1px solid var(--border-subtle)", borderRadius: 6 }}>
          <div style={{ color: "var(--fg2)", fontSize: 10, textTransform: "uppercase", letterSpacing: ".06em", fontWeight: 700 }}>Cadence</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--fg1)" }}>148 wpm</div>
        </div>
        <div style={{ padding: "6px 8px", background: "var(--surface-bg)", border: "1px solid var(--border-subtle)", borderRadius: 6 }}>
          <div style={{ color: "var(--fg2)", fontSize: 10, textTransform: "uppercase", letterSpacing: ".06em", fontWeight: 700 }}>Filler ratio</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "var(--fg1)" }}>2.1%</div>
        </div>
      </div>
    </div>
  );
}

function ChatTab({ chat, slides, segmentsById, onJumpToSegment, placements, onUnplace, onPlaceAtActive }) {
  // Group chats by the slide their anchor segment falls under (auto-scroll-by-slide dividers).
  const grouped = useMemo(() => {
    const out = [];
    let curSlide = null;
    chat.forEach((c) => {
      const seg = segmentsById.get(c.anchor);
      const sl = seg ? slides.find((s) => s.id === seg.slide_id) : null;
      if (sl && sl.id !== curSlide) {
        out.push({ divider: true, slide: sl });
        curSlide = sl.id;
      }
      out.push({ divider: false, msg: c, seg });
    });
    return out;
  }, [chat, slides, segmentsById]);

  const placedCount = chat.filter((c) => placements && placements[c.id]).length;

  return (
    <div>
      <div className="rightrail__sectionhead" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>Chat · {chat.length}</span>
        <span style={{ color: "var(--color-green)" }}>{placedCount} placed</span>
      </div>
      {grouped.map((row, i) => {
        if (row.divider) {
          const placedSeg = placements && Object.entries(placements).find(([cid, sid]) => sid && chat.find((cc) => cc.id === cid)?.anchor === row.slide.id);
          return <div key={"d" + i} className="chat-divider">Slide {String(row.slide.n).padStart(2, "0")} · {row.slide.title.length > 32 ? row.slide.title.slice(0, 32) + "…" : row.slide.title}</div>;
        }
        const isPlaced = placements && placements[row.msg.id];
        const placedSeg = isPlaced && segmentsById.get(isPlaced);
        const placedSlide = placedSeg ? slides.find((s) => s.id === placedSeg.slide_id) : null;
        return (
          <div key={row.msg.id} className={`chat-msg ${isPlaced ? "is-placed" : ""}`}
               draggable={!isPlaced}
               onDragStart={(e) => { e.dataTransfer.setData("application/vnd.mic.anchor", row.msg.id); e.dataTransfer.effectAllowed = "move"; }}>
            <div className="chat-msg__head">
              <Avatar name={row.msg.author.replace(/^Dr\. /, "")} size={20} ring={false} />
              <span className="chat-msg__author">{row.msg.author}</span>
              <span className="chat-msg__t">{fmtTime(row.msg.t)}</span>
            </div>
            <div className="chat-msg__body">{row.msg.text}</div>
            <div className="chat-msg__foot">
              {isPlaced ? (
                <>
                  <span className="chat-msg__placed">
                    <Icon name="anchor" size={10} /> PLACED · Slide {placedSlide ? String(placedSlide.n).padStart(2, "0") : "?"}
                  </span>
                  <button className="chat-msg__unplace" onClick={() => onUnplace(row.msg.id)}>× Remove</button>
                </>
              ) : (
                <>
                  <span className="chat-msg__draghint">⠿ drag to segment</span>
                  <button className="chat-msg__place" onClick={() => onPlaceAtActive(row.msg.id)}>Place at active</button>
                </>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PollsTab({ polls, segmentsById, onJumpToSegment, placements, onUnplace, onPlaceAtActive, slides = MIC_DATA.SLIDES }) {
  const placedCount = polls.filter((p) => placements && placements[p.id]).length;
  return (
    <div>
      <div className="rightrail__sectionhead" style={{ display: "flex", justifyContent: "space-between" }}>
        <span>Polls · {polls.length}</span>
        <span style={{ color: "var(--color-green)" }}>{placedCount} placed</span>
      </div>
      {polls.map((p) => {
        const winnerVotes = Math.max(...p.options.map((o) => o.votes));
        const isPlaced = placements && placements[p.id];
        const placedSeg = isPlaced && segmentsById.get(isPlaced);
        const placedSlide = placedSeg ? slides.find((s) => s.id === placedSeg.slide_id) : null;
        return (
          <div key={p.id} className={`poll-card ${isPlaced ? "is-placed" : ""}`}
               draggable={!isPlaced}
               onDragStart={(e) => { e.dataTransfer.setData("application/vnd.mic.anchor", p.id); e.dataTransfer.effectAllowed = "move"; }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              {isPlaced ? (
                <span className="chat-msg__placed">PLACED · Slide {placedSlide ? String(placedSlide.n).padStart(2, "0") : "?"}</span>
              ) : (
                <span className="chip chip--gold" style={{ fontSize: 9 }}>Poll · {p.status}</span>
              )}
              {isPlaced
                ? <button className="chat-msg__unplace" onClick={() => onUnplace(p.id)}>× Remove</button>
                : <button className="chat-msg__place" onClick={() => onPlaceAtActive(p.id)}>Place</button>}
            </div>
            <p className="poll-card__q">{p.question}</p>
            {p.options.map((opt) => {
              const pct = Math.round((opt.votes / p.total) * 100);
              const isWinner = opt.votes === winnerVotes;
              return (
                <div key={opt.id} className={`poll-card__opt ${isWinner ? "is-winner" : ""}`}>
                  <div className="poll-card__opt-bar" style={{ width: `${pct}%` }} />
                  <div className="poll-card__opt-row">
                    <span className="poll-card__opt-label">{opt.label}</span>
                    <span className="poll-card__opt-pct">{pct}% · {opt.votes}</span>
                  </div>
                </div>
              );
            })}
            <div className="poll-card__foot">
              <span>Total: {p.total} votes</span>
              {!isPlaced ? <span style={{ color: "var(--fg2)", fontSize: 11 }}>⠿ drag to segment</span> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Anchor block (inline poll/chat segments in transcript) ─
function AnchorBlock({ item, kind, slide, onRemove, onJumpToSegment }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(kind === "chat" ? item.text : item.question);
  const cls = ["segment", "segment--anchor", `segment--anchor-${kind}`];
  const accent = kind === "poll" ? "var(--color-green)" : "var(--color-gold)";

  const save = () => {
    auditLog.log("You", kind === "chat" ? "chat_edit" : "poll_edit", `Edited ${item.id} ${kind === "chat" ? "message" : "question"}`);
    toast.push(`${kind === "chat" ? "Chat message" : "Poll"} saved`, { tone: "ok" });
    setEditing(false);
  };

  return (
    <article className={cls.join(" ")} data-anchor-id={item.id} draggable={!editing} onDragStart={(e) => e.stopPropagation()}>
      <header className="segment__header">
        <span className="segment__slide-chip">
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: accent }} />
          <strong>{slide ? String(slide.n).padStart(2, "0") : "—"}</strong>
          <span style={{ opacity: 0.5 }}>·</span>
          <span>{kind === "poll" ? `Poll · ${item.question.slice(0, 60)}${item.question.length > 60 ? "…" : ""}` : `Chat · ${item.author}`}</span>
        </span>
        <span className="segment__inline-actions">
          {kind === "poll"
            ? <span className="chip chip--green" style={{ fontSize: 9, padding: "2px 7px" }}><Icon name="list" size={9} /> Poll</span>
            : <span className="chip chip--gold" style={{ fontSize: 9, padding: "2px 7px" }}><Icon name="message" size={9} /> Chat</span>}
          {!editing ? (
            <button className="segment__inline-action" onClick={(e) => { e.stopPropagation(); setEditing(true); setDraft(kind === "chat" ? item.text : item.question); }}>Edit</button>
          ) : null}
          <button className="segment__inline-action segment__inline-action--danger" onClick={(e) => { e.stopPropagation(); onRemove(item.id); }}>
            <Icon name="x" size={10} /> Remove
          </button>
        </span>
      </header>
      <div className="segment__body">
        <div className="segment__gutter">
          <span className="segment__time">{fmtTime(item.t)}</span>
          <span className="segment__speaker-pill" style={{ color: accent }}>
            {kind === "poll" ? "Poll" : "Chat"}
          </span>
        </div>
        <div className="segment__main">
          {editing ? (
            <div className="segment-editor" style={{ width: "100%" }}>
              <textarea
                className="segment-editor__textarea"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onClick={(e) => e.stopPropagation()}
                autoFocus
                wrap="soft"
                style={{ width: "100%", minHeight: kind === "poll" ? 60 : 110 }}
                rows={kind === "poll" ? 2 : 4}
              />
              {kind === "poll" ? (
                <div style={{ padding: "8px 14px", borderTop: "1px solid var(--border-subtle)", background: "var(--surface-bg)" }}>
                  <div className="impv-lbl" style={{ marginBottom: 8 }}>Options ({item.options.length})</div>
                  {item.options.map((opt) => (
                    <div key={opt.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <input defaultValue={opt.label} className="impv-input" style={{ flex: 1, fontSize: 12.5, padding: "5px 8px" }} />
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg2)", width: 56, textAlign: "right" }}>{opt.votes} votes</span>
                    </div>
                  ))}
                </div>
              ) : null}
              <div className="segment-editor__foot">
                <button className="btn btn--secondary btn--sm" onClick={(e) => { e.stopPropagation(); setEditing(false); }}>Cancel</button>
                <button className="btn btn--sm" style={{ background: "var(--color-green)", color: "#fff" }} onClick={(e) => { e.stopPropagation(); save(); }}>Save</button>
              </div>
            </div>
          ) : kind === "chat" ? (
            <div style={{ fontSize: 14, lineHeight: 1.55, color: "var(--fg1)" }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>{item.author}:</div>
              <div>{item.text}</div>
            </div>
          ) : (
            <div className="anchor-poll">
              <div className="anchor-poll__q">{item.question}</div>
              {item.options.map((opt) => {
                const pct = Math.round((opt.votes / item.total) * 100);
                const isWinner = opt.votes === Math.max(...item.options.map((o) => o.votes));
                return (
                  <div key={opt.id} className={`anchor-poll__row ${isWinner ? "is-winner" : ""}`}>
                    <span className="anchor-poll__pct">{pct}%</span>
                    <div className="anchor-poll__bar"><span style={{ width: `${pct}%` }} /></div>
                    <span className="anchor-poll__lbl">{opt.label}</span>
                  </div>
                );
              })}
              <div className="anchor-poll__total">{item.total} responses</div>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

// ── Transcript pane ────────────────────────────────────────
function TranscriptPane({
  segments, activeSegmentId, activeWordIdx, focusedSlideId, slideRailMode,
  onSegmentClick, onWordClick, editingSegmentId, onEditEnd, onClearFocus, density,
  anchorsBySegment, onRemoveAnchor, onJumpToSegment, onDropOnSegment,
}) {
  const scrollRef = useRef(null);
  const editorTextareaRef = useRef(null);
  // Inline editor state: { segId, mode: 'edit'|'reassign'|'speaker', draft, draftSpeaker, draftSlide, history, redo }
  const [inline, setInline] = useState(null);
  const startEdit = (seg) => setInline({ segId: seg.id, mode: "edit", draft: `**${MIC_DATA.SPEAKERS[seg.speaker].short}:** ${seg.text}`, history: [], redo: [] });
  const startReassign = (seg) => setInline({ segId: seg.id, mode: "reassign" });
  const startSpeaker = (seg) => setInline({ segId: seg.id, mode: "speaker", draftSpeaker: seg.speaker });
  const closeInline = () => setInline(null);
  const saveEdit = (seg) => {
    auditLog.log("You", "edit", `Edited ${seg.id}`);
    toast.push("Segment saved", { tone: "ok" });
    closeInline();
  };
  const saveReassign = (seg, slideId) => {
    const sl = MIC_DATA.SLIDES.find((s) => s.id === slideId);
    auditLog.log("You", "reassign_segment", `Moved ${seg.id} → slide ${sl?.n} (${sl?.title})`);
    toast.push(`Reassigned to slide ${sl?.n}`, { tone: "ok" });
    closeInline();
  };
  const saveSpeaker = (seg, speakerKey) => {
    const sp = MIC_DATA.SPEAKERS[speakerKey];
    auditLog.log("You", "speaker_reassignment", `${seg.id} speaker → ${sp?.name}`);
    toast.push(`Speaker → ${sp?.short}`, { tone: "ok" });
    closeInline();
  };
  // ── Toolbar action helpers (read selection from the ref, push history)
  const _mutate = (next, selOffset) => {
    setInline((prev) => prev ? { ...prev, draft: next, history: [...(prev.history || []), prev.draft], redo: [] } : prev);
    // Restore focus + caret on next frame
    requestAnimationFrame(() => {
      const ta = editorTextareaRef.current;
      if (!ta) return;
      ta.focus();
      if (selOffset != null) { ta.selectionStart = selOffset.start; ta.selectionEnd = selOffset.end; }
    });
  };
  const tbWrap = (before, after = before) => {
    const ta = editorTextareaRef.current;
    if (!ta || !inline) return;
    const s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
    const sel = v.slice(s, e) || "text";
    const next = v.slice(0, s) + before + sel + after + v.slice(e);
    _mutate(next, { start: s + before.length, end: s + before.length + sel.length });
  };
  const tbLine = (prefix) => {
    const ta = editorTextareaRef.current;
    if (!ta || !inline) return;
    const s = ta.selectionStart, v = ta.value;
    const lineStart = v.lastIndexOf("\n", s - 1) + 1;
    const next = v.slice(0, lineStart) + prefix + v.slice(lineStart);
    _mutate(next, { start: s + prefix.length, end: s + prefix.length });
  };
  const tbInsert = (text) => {
    const ta = editorTextareaRef.current;
    if (!ta || !inline) return;
    const s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
    const next = v.slice(0, s) + text + v.slice(e);
    _mutate(next, { start: s + text.length, end: s + text.length });
  };
  const tbUndo = () => {
    setInline((prev) => {
      if (!prev || !prev.history || !prev.history.length) return prev;
      const last = prev.history[prev.history.length - 1];
      return { ...prev, draft: last, history: prev.history.slice(0, -1), redo: [...(prev.redo || []), prev.draft] };
    });
  };
  const tbRedo = () => {
    setInline((prev) => {
      if (!prev || !prev.redo || !prev.redo.length) return prev;
      const next = prev.redo[prev.redo.length - 1];
      return { ...prev, draft: next, history: [...(prev.history || []), prev.draft], redo: prev.redo.slice(0, -1) };
    });
  };
  const tbClearMarks = () => {
    if (!inline) return;
    const ta = editorTextareaRef.current;
    const cleared = inline.draft.replace(/\{\{(uncertain|verified|drift):([^}]+)\}\}/g, "$2");
    _mutate(cleared, ta ? { start: ta.selectionStart, end: ta.selectionEnd } : null);
  };
  const tbLink = () => {
    const url = window.prompt("URL:", "https://");
    if (url) tbWrap("[", `](${url})`);
  };

  // Auto-scroll to active segment
  useEffect(() => {
    if (!activeSegmentId || !scrollRef.current) return;
    const el = scrollRef.current.querySelector(`[data-seg-id="${activeSegmentId}"]`);
    if (!el) return;
    const box = scrollRef.current.getBoundingClientRect();
    const eb = el.getBoundingClientRect();
    if (eb.top < box.top + 60 || eb.bottom > box.bottom - 60) {
      scrollRef.current.scrollTo({
        top: el.offsetTop - 80,
        behavior: "smooth",
      });
    }
  }, [activeSegmentId]);

  const visible = useMemo(() => {
    if (slideRailMode === "filter" && focusedSlideId) {
      return segments.filter((s) => s.slide_id === focusedSlideId);
    }
    return segments;
  }, [segments, slideRailMode, focusedSlideId]);

  return (
    <section className="transcript" ref={scrollRef} role="region" aria-label="Transcript" data-screen-label="Transcript">
      {slideRailMode === "filter" && focusedSlideId ? (
        <div className="transcript__filter-banner" role="status">
          <Icon name="filter" size={14} />
          <span><strong>Filter mode:</strong> showing {visible.length} segments on slide {focusedSlideId.replace("s", "")}.</span>
          <button className="btn btn--tertiary btn--sm" onClick={onClearFocus}>Clear filter</button>
        </div>
      ) : null}

      {visible.map((seg) => {
        const sp = MIC_DATA.SPEAKERS[seg.speaker];
        const sl = slideById(seg.slide_id);
        const accent = slideAccent(seg.slide_id);
        const cls = ["segment"];
        if (seg.id === activeSegmentId) cls.push("is-active");
        if (slideRailMode === "focus" && seg.slide_id === focusedSlideId) cls.push("is-focused-slide");
        if (seg.needs_review) cls.push("is-needs-review");
        if (seg.id === editingSegmentId) cls.push("is-editing");
        const speakerCls = `speaker-${seg.speaker}`;
        const anchors = (anchorsBySegment && anchorsBySegment.get(seg.id)) || [];
        return (
          <React.Fragment key={seg.id}>
          <article
            data-seg-id={seg.id}
            className={cls.join(" ")}
            style={{ boxShadow: `inset 3px 0 0 ${accent}` }}
            onClick={() => onSegmentClick(seg.id)}
            onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("is-drop-target"); }}
            onDragLeave={(e) => e.currentTarget.classList.remove("is-drop-target")}
            onDrop={(e) => {
              e.preventDefault();
              e.currentTarget.classList.remove("is-drop-target");
              const data = e.dataTransfer.getData("application/vnd.mic.anchor");
              if (data && onDropOnSegment) onDropOnSegment(data, seg.id);
            }}>
            <header className="segment__header">
              <span className="segment__slide-chip">
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: accent }} />
                <strong>{sl ? String(sl.n).padStart(2, "0") : "—"}</strong>
                <span style={{ opacity: 0.5 }}>·</span>
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{sl?.title || "Unassigned"}</span>
              </span>
              <span className="segment__inline-actions">
                {inline && inline.segId === seg.id ? null : (
                  <>
                    <button className="segment__inline-action" data-test-id="seg-edit" onClick={(e) => { e.stopPropagation(); startEdit(seg); }}>Edit</button>
                    <button className="segment__inline-action" data-test-id="seg-reassign" onClick={(e) => { e.stopPropagation(); startReassign(seg); }}>Reassign</button>
                    <button className="segment__inline-action" data-test-id="seg-speaker" onClick={(e) => { e.stopPropagation(); startSpeaker(seg); }}>Speaker</button>
                  </>
                )}
                {inline && inline.segId === seg.id && inline.mode === "speaker" ? (
                  <>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "2px 8px", border: "1px solid var(--border-subtle)", borderRadius: 999, fontSize: 11.5 }}>
                      <Icon name="message" size={10} />
                      <strong style={{ color: MIC_DATA.SPEAKERS[seg.speaker]?.color }}>{MIC_DATA.SPEAKERS[seg.speaker]?.name?.replace(/, DVM.*/, "") || ""} – VIN</strong>
                    </span>
                    <button className="segment__inline-action" onClick={(e) => { e.stopPropagation(); }}>Edit</button>
                    <button className="segment__inline-action segment__inline-action--danger" onClick={(e) => { e.stopPropagation(); closeInline(); }}><Icon name="x" size={10} /> Remove</button>
                  </>
                ) : null}
              </span>
            </header>
            <div className="segment__body">
              <div className="segment__gutter">
                <span className="segment__time">{fmtTime(seg.start)}</span>
                <span className={`segment__speaker-pill ${speakerCls}`}>{sp.short}</span>
              </div>
              <div className="segment__main">
                {inline && inline.segId === seg.id && inline.mode === "edit" ? (
                  <div className="segment-editor">
                    <div className="segment-editor__toolbar" onMouseDown={(e) => e.preventDefault()}>
                      <button type="button" className="segment-editor__btn" title="Bold"            onMouseDown={(e) => e.preventDefault()} onClick={() => tbWrap("**")}><strong>B</strong></button>
                      <button type="button" className="segment-editor__btn" title="Italic"          onMouseDown={(e) => e.preventDefault()} onClick={() => tbWrap("*")}><em>I</em></button>
                      <button type="button" className="segment-editor__btn" title="Underline"       onMouseDown={(e) => e.preventDefault()} onClick={() => tbWrap("__")}><u>U</u></button>
                      <span className="segment-editor__sep" />
                      <button type="button" className="segment-editor__btn" title="Bullet list"     onMouseDown={(e) => e.preventDefault()} onClick={() => tbLine("- ")}>•</button>
                      <button type="button" className="segment-editor__btn" title="Numbered list"   onMouseDown={(e) => e.preventDefault()} onClick={() => tbLine("1. ")}>1.</button>
                      <span className="segment-editor__sep" />
                      <button type="button" className="segment-editor__btn" title="Undo"            onMouseDown={(e) => e.preventDefault()} onClick={tbUndo}>↩</button>
                      <button type="button" className="segment-editor__btn" title="Redo"            onMouseDown={(e) => e.preventDefault()} onClick={tbRedo}>↪</button>
                      <button type="button" className="segment-editor__btn" title="Strikethrough"   onMouseDown={(e) => e.preventDefault()} onClick={() => tbWrap("~~")}><s>S</s></button>
                      <span className="segment-editor__sep" />
                      <button type="button" className="segment-editor__btn" title="Mark uncertain"  onMouseDown={(e) => e.preventDefault()} onClick={() => tbWrap("{{uncertain:", "}}")}><span style={{ width: 14, height: 14, borderRadius: "50%", background: "#facc15", display: "inline-block" }} /></button>
                      <button type="button" className="segment-editor__btn" title="Mark verified"   onMouseDown={(e) => e.preventDefault()} onClick={() => tbWrap("{{verified:", "}}")}><span style={{ width: 14, height: 14, borderRadius: "50%", background: "#22c55e", display: "inline-block" }} /></button>
                      <button type="button" className="segment-editor__btn" title="Mark drift"      onMouseDown={(e) => e.preventDefault()} onClick={() => tbWrap("{{drift:", "}}")}><span style={{ width: 14, height: 14, borderRadius: "50%", background: "#3b82f6", display: "inline-block" }} /></button>
                      <button type="button" className="segment-editor__btn" title="Clear marks"     onMouseDown={(e) => e.preventDefault()} onClick={tbClearMarks}><span style={{ width: 14, height: 14, borderRadius: "50%", background: "#f9a8d4", display: "inline-block" }} /></button>
                      <span className="segment-editor__sep" />
                      <button type="button" className="segment-editor__btn" title="Insert link"     onMouseDown={(e) => e.preventDefault()} onClick={tbLink}><Icon name="anchor" size={12} /></button>
                      <button type="button" className="segment-editor__btn" title="Insert poll reference" onMouseDown={(e) => e.preventDefault()} onClick={() => tbInsert(" {{poll}}")}><Icon name="list" size={12} /></button>
                    </div>
                    <textarea
                      ref={editorTextareaRef}
                      className="segment-editor__textarea"
                      value={inline.draft}
                      onChange={(e) => setInline((p) => p ? { ...p, draft: e.target.value, history: [...(p.history || []), p.draft].slice(-50), redo: [] } : p)}
                      onClick={(e) => e.stopPropagation()}
                      autoFocus
                      wrap="soft"
                      style={{ width: "100%" }}
                      rows={Math.max(3, Math.ceil(inline.draft.length / 90))}
                    />
                    <div className="segment-editor__foot">
                      <button className="btn btn--secondary btn--sm" onClick={(e) => { e.stopPropagation(); closeInline(); }}>Cancel</button>
                      <button className="btn btn--sm" style={{ background: "var(--color-green)", color: "#fff" }} onClick={(e) => { e.stopPropagation(); saveEdit(seg); }}>Save</button>
                    </div>
                  </div>
                ) : inline && inline.segId === seg.id && inline.mode === "reassign" ? (
                  <div className="segment-reassign">
                    {MIC_DATA.SLIDES.map((sl) => (
                      <button key={sl.id} className={`segment-reassign__tile ${sl.id === seg.slide_id ? "is-current" : ""}`}
                              onClick={(e) => { e.stopPropagation(); saveReassign(seg, sl.id); }}>
                        <span className="segment-reassign__dot" style={{ background: slideAccent(sl.id) }} />
                        <strong>{String(sl.n).padStart(2, "0")}</strong>
                        <span style={{ opacity: 0.4 }}>·</span>
                        <span className="segment-reassign__title">{sl.title.replace(/^(Title — |Case Study \d+ — )/, "")}</span>
                      </button>
                    ))}
                    <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                      <button className="btn btn--secondary btn--sm" onClick={(e) => { e.stopPropagation(); closeInline(); }}>Cancel</button>
                    </div>
                  </div>
                ) : inline && inline.segId === seg.id && inline.mode === "speaker" ? (
                  <div className="segment-speakerpick">
                    {Object.entries(MIC_DATA.SPEAKERS).map(([key, sp]) => (
                      <button key={key} className={`segment-speakerpick__tile ${key === inline.draftSpeaker ? "is-current" : ""}`}
                              onClick={(e) => { e.stopPropagation(); saveSpeaker(seg, key); }}>
                        <span className="segment-speakerpick__avatar" style={{ background: sp.color }}>{sp.short.split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase()}</span>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: 12.5 }}>{sp.name}</div>
                          <div style={{ fontSize: 11, color: "var(--fg2)" }}>{sp.role}</div>
                        </div>
                      </button>
                    ))}
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                      <button className="btn btn--secondary btn--sm" onClick={(e) => { e.stopPropagation(); closeInline(); }}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <SegmentText
                      text={seg.text}
                      flags={seg.ai_flags}
                      activeWordIdx={seg.id === activeSegmentId ? activeWordIdx : -1}
                      onWordClick={(w) => onWordClick(seg.id, w)}
                    />
                    <div className="segment__chiprow">
                      {seg.needs_review ? (
                        <span className="segment__chip" style={{ background: "rgba(183,93,4,0.10)", color: "var(--color-amber)", borderColor: "rgba(183,93,4,0.3)" }}>
                          <Icon name="flag" /> needs review
                        </span>
                      ) : null}
                      {seg.confidence === "low" ? (
                        <span className="segment__chip" style={{ background: "rgba(8,97,206,0.08)", color: "var(--color-blue)", borderColor: "rgba(8,97,206,0.25)" }}>
                          <Icon name="alert" /> low confidence
                        </span>
                      ) : null}
                      {seg.ai_flags.length > 0 ? (
                        <span className="segment__chip" style={{ background: "rgba(197,70,68,0.06)", color: "var(--color-red)", borderColor: "rgba(197,70,68,0.25)" }}>
                          <Icon name="lightning" /> {seg.ai_flags.length} AI flag{seg.ai_flags.length === 1 ? "" : "s"}
                        </span>
                      ) : null}
                      {seg.has_user_override ? (
                        <span className="segment__chip" style={{ background: "rgba(0,40,85,0.08)", color: "var(--color-navy)" }}>
                          <Icon name="edit" /> user override
                        </span>
                      ) : null}
                    </div>
                  </>
                )}
              </div>
            </div>
          </article>
          {anchors.map((a) => (
            <AnchorBlock
              key={a.id}
              item={a}
              kind={a.kind}
              slide={sl}
              onRemove={(id) => onRemoveAnchor && onRemoveAnchor(id)}
              onJumpToSegment={onJumpToSegment}
            />
          ))}
          </React.Fragment>
        );
      })}
      <div style={{ padding: "24px 12px", textAlign: "center", color: "var(--fg2)", fontSize: 12 }}>
        End of transcript · {visible.length} segments rendered (virtualized)
      </div>
    </section>
  );
}

// ── STT reference pane — orthogonal to base_text (§9, L2) ──
// Renders raw STT tokens with timing. Deliberately distinct from the AI Transcript:
// monospace, dark surface, lowercase, fillers visible, no edits, no AI flag overlays.
function STTPane({ segments, activeSegmentId, activeWordIdx, onSegmentClick, onWordClick, time, focusedSlideId, slideRailMode, onClearFocus }) {
  const scrollRef = useRef(null);

  const visible = useMemo(() => {
    if (slideRailMode === "filter" && focusedSlideId) {
      return segments.filter((s) => s.slide_id === focusedSlideId);
    }
    return segments;
  }, [segments, slideRailMode, focusedSlideId]);

  // Generate STT-looking tokens from base_text + the discrepancy map (which gives us
  // the "raw STT" alternative). In a real system these come straight from the STT JSON.
  const sttBySegId = useMemo(() => {
    const drift = new Map();
    MIC_DATA.DISCREPANCIES.forEach((d) => { drift.set(d.seg, d); });
    const fillers = ["um", "uh", "you know", "like"];
    const m = new Map();
    segments.forEach((seg, i) => {
      const words = seg.text.toLowerCase().replace(/[.,;!?—–]/g, "").split(/\s+/);
      const tokens = [];
      const dur = Math.max(0.1, seg.end - seg.start);
      const perWord = dur / words.length;
      const drow = drift.get(seg.id);
      // Inject a filler at the start of every 4th segment to make the contrast vivid.
      if (i % 4 === 0) {
        tokens.push({ kind: "filler", text: fillers[i % fillers.length], t: seg.start });
      }
      words.forEach((w, j) => {
        let cls = null;
        let text = w;
        if (drow && drow.kind === "drift") {
          // Replace the first occurrence of base_text fragment with the STT version
          const baseFirstWord = drow.base.toLowerCase().split(/\s+/)[0];
          if (w === baseFirstWord) {
            text = drow.stt.toLowerCase().split(/\s+/).join(" ");
            cls = "drift";
          }
        }
        tokens.push({ kind: cls, text, t: +(seg.start + j * perWord).toFixed(2) });
      });
      m.set(seg.id, tokens);
    });
    return m;
  }, [segments]);

  useEffect(() => {
    if (!activeSegmentId || !scrollRef.current) return;
    const el = scrollRef.current.querySelector(`[data-stt-seg="${activeSegmentId}"]`);
    if (!el) return;
    const box = scrollRef.current.getBoundingClientRect();
    const eb = el.getBoundingClientRect();
    if (eb.top < box.top + 60 || eb.bottom > box.bottom - 60) {
      scrollRef.current.scrollTo({ top: el.offsetTop - 80, behavior: "smooth" });
    }
  }, [activeSegmentId]);

  return (
    <section className="stt-pane" ref={scrollRef} aria-label="STT reference" data-screen-label="STT Reference">
      <div className="stt-pane__banner" role="note">
        <Icon name="alert" size={16} />
        <div>
          <strong>STT reference · orthogonal pipeline.</strong> Raw Google STT tokens used only for playback
          synchronization, word highlighting, and discrepancy classification. These tokens <em>never</em> appear
          in <code style={{ background: "rgba(255,255,255,0.08)", padding: "1px 5px", borderRadius: 2 }}>base_text</code>,
          never participate in correction lineage, and are never user-editable.
          Verified by pipeline-isolation test · L2.
        </div>
        <span className="chip" style={{ background: "rgba(0,151,169,0.18)", color: "#fff", borderColor: "rgba(0,151,169,0.5)" }}>
          read-only
        </span>
      </div>

      {slideRailMode === "filter" && focusedSlideId ? (
        <div className="transcript__filter-banner" role="status" style={{ background: "rgba(0,151,169,0.08)", borderColor: "rgba(0,151,169,0.35)", color: "var(--color-teal)" }}>
          <Icon name="filter" size={14} />
          <span><strong>Filter mode:</strong> showing {visible.length} STT segments on slide {focusedSlideId.replace("s", "")}.</span>
          <button className="btn btn--tertiary btn--sm" onClick={onClearFocus}>Clear filter</button>
        </div>
      ) : null}

      {visible.map((seg) => {
        const tokens = sttBySegId.get(seg.id) || [];
        const isActive = seg.id === activeSegmentId;
        const cls = ["stt-segment"];
        if (isActive) cls.push("is-active");
        // Map active word index in base_text to approximate token index in STT.
        let nonFillerCount = -1;
        const accent = slideAccent(seg.slide_id);
        const sl = slideById(seg.slide_id);
        return (
          <article key={seg.id} data-stt-seg={seg.id} className={cls.join(" ")} style={{ boxShadow: `inset 3px 0 0 ${accent}` }} onClick={() => onSegmentClick(seg.id)}>
            <div className="stt-segment__gutter">
              <span className="stt-segment__time">{fmtTime(seg.start)}</span>
              <span className={`stt-segment__conf ${seg.confidence === "low" ? "low" : ""}`}>
                {seg.confidence === "low" ? "conf 0.61" : `conf 0.${82 + (seg.idx % 14)}`}
              </span>
              <span className="stt-segment__conf" style={{ fontFamily: "var(--font-mono)", color: accent, borderColor: withAlpha(accent, "44") }}>
                {sl ? `s${String(sl.n).padStart(2, "0")}` : seg.id}
              </span>
            </div>
            <div className="stt-segment__main">
              {tokens.map((tok, i) => {
                if (tok.kind === "filler") {
                  return <span key={i} className="stt-token stt-token--filler">[{tok.text}]&nbsp;</span>;
                }
                nonFillerCount++;
                const tokenIsCurrent = isActive && nonFillerCount === activeWordIdx;
                const cls2 = ["stt-token"];
                if (tok.kind === "drift") cls2.push("stt-token--drift");
                if (tokenIsCurrent) cls2.push("is-current");
                const tIdx = nonFillerCount;
                return (
                  <span key={i} className={cls2.join(" ")} onClick={(e) => { e.stopPropagation(); onWordClick(seg.id, tIdx); }}>
                    {tok.text}<span className="t">{tok.t.toFixed(1)}</span>{" "}
                  </span>
                );
              })}
            </div>
          </article>
        );
      })}
      <div style={{ padding: "24px 12px", textAlign: "center", color: "rgba(255,255,255,0.4)", fontSize: 11, fontFamily: "var(--font-family)" }}>
        End of STT stream · {visible.length} segments · superscript = token start (s) · drift highlights match discrepancy classification
      </div>
    </section>
  );
}

function STTSidePanel({ time, totalDuration, segments }) {
  const flagged = MIC_DATA.DISCREPANCIES;
  const driftCount = flagged.filter((d) => d.kind === "drift").length;
  const punctCount = flagged.filter((d) => d.kind === "punctuation").length;
  const fillerCount = flagged.filter((d) => d.kind === "filler").length;
  const lowConfCount = flagged.filter((d) => d.kind === "low_confidence").length;
  return (
    <aside className="stt-side" aria-label="STT debug panel" data-screen-label="STT Debug Panel">
      <h4>STT Stream</h4>
      <div className="stt-side__row"><span>Engine</span><span>Google STT v3</span></div>
      <div className="stt-side__row"><span>Model</span><span>latest_long</span></div>
      <div className="stt-side__row"><span>Sample rate</span><span>48 kHz</span></div>
      <div className="stt-side__row"><span>Channels</span><span>mono</span></div>
      <div className="stt-side__row"><span>Stream depth</span><span>{segments.length} segs</span></div>
      <div className="stt-side__row"><span>Cursor</span><span>{fmtTime(time)} / {fmtTime(totalDuration)}</span></div>

      <h4>Token Distribution</h4>
      <div className="stt-side__row"><span>drift</span><span style={{ color: "var(--color-red)" }}>{driftCount}</span></div>
      <div className="stt-side__row"><span>punctuation</span><span>{punctCount}</span></div>
      <div className="stt-side__row"><span>filler</span><span style={{ color: "var(--color-amber)" }}>{fillerCount}</span></div>
      <div className="stt-side__row"><span>low_confidence</span><span style={{ color: "#6FA9F0" }}>{lowConfCount}</span></div>

      <h4>Legend</h4>
      <div className="stt-side__legend">
        <div><code className="stt-token stt-token--drift">fifty</code><span>drift vs base_text</span></div>
        <div><code className="stt-token stt-token--filler">[um]</code><span>recognised filler</span></div>
        <div><code style={{ background: "var(--color-gold)", color: "var(--color-navy)", padding: "1px 6px", borderRadius: 3 }}>word</code><span>current playback word</span></div>
        <div><code>word<sup style={{ fontSize: 8, opacity: 0.5 }}>12.4</sup></code><span>token start time (s)</span></div>
      </div>

      <h4>Invariants</h4>
      <div style={{ fontSize: 11, fontFamily: "var(--font-family)", lineHeight: 1.55, color: "var(--color-light-steel)" }}>
        <p style={{ margin: "0 0 8px" }}>
          <span className="chip chip--green" style={{ marginRight: 4 }}><Icon name="check" size={10} /> L2</span>
          STT tokens never participate in correction lineage.
        </p>
        <p style={{ margin: "0 0 8px" }}>
          <span className="chip chip--green" style={{ marginRight: 4 }}><Icon name="check" size={10} /> §9</span>
          Pipeline isolation test verifies separate stores; no cross-references.
        </p>
        <p style={{ margin: 0 }}>
          <span className="chip chip--green" style={{ marginRight: 4 }}><Icon name="check" size={10} /> §15.1</span>
          STT tab is reference-only — no edit controls rendered.
        </p>
      </div>
    </aside>
  );
}

// ── Editor Route ──────────────────────────────────────────
function DownloadMenu({ code }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  const formats = [
    { ext: "docx", label: "Word",      sub: "Macro-compatible transcript" },
    { ext: "srt",  label: "Captions",  sub: "SubRip for Wistia / video player" },
    { ext: "txt",  label: "Plain Text", sub: "Quick paste / email" },
    { ext: "zip",  label: "Word Macro", sub: "One-time install for SRT/CMS prep" },
  ];
  return (
    <span ref={ref} className="dl-menu-wrap">
      <button className={`btn btn--primary btn--sm ${open ? "dl-menu-trigger--open" : ""}`} data-test-id="editor-download" onClick={() => setOpen((v) => !v)}>
        <Icon name="download" /> Download
      </button>
      {open ? (
        <div className="dl-menu" role="menu">
          {formats.map((f) => (
            <button key={f.ext} className="dl-menu__item" role="menuitem" data-test-id={`dl-${f.ext}`} onClick={() => { setOpen(false); wired.download(f.ext, code); }}>
              <div className="dl-menu__label">{f.label} <code>(.{f.ext})</code></div>
              <div className="dl-menu__sub">{f.sub}</div>
            </button>
          ))}
        </div>
      ) : null}
    </span>
  );
}

function EditorRoute({ id, initialTab }) {
  const session = MIC_DATA.SESSIONS.find((s) => s.id === id) || MIC_DATA.SESSIONS[0];
  const segments = MIC_DATA.SEGMENTS;
  const slides   = MIC_DATA.SLIDES;
  const total    = MIC_DATA.TOTAL_DURATION;

  const segmentsById = useMemo(() => {
    const m = new Map();
    segments.forEach((s) => m.set(s.id, s));
    return m;
  }, [segments]);
  const segmentsBySlide = useMemo(() => {
    const m = new Map();
    slides.forEach((sl) => m.set(sl.id, []));
    segments.forEach((s) => { if (s.slide_id) m.get(s.slide_id)?.push(s); });
    return m;
  }, [segments, slides]);

  // ── Playback state — restore from localStorage
  const [time, setTime] = useState(() => {
    const v = parseFloat(localStorage.getItem(`mic_playback_${id}`));
    return isNaN(v) ? 198 : v; // default near slide 6 demo position
  });
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [cc, setCc] = useState(true);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(0.85);
  const rafRef = useRef(0);
  const lastTickRef = useRef(0);

  useEffect(() => {
    localStorage.setItem(`mic_playback_${id}`, String(time));
  }, [time, id]);

  useEffect(() => {
    if (!playing) {
      cancelAnimationFrame(rafRef.current);
      return;
    }
    const step = (now) => {
      if (!lastTickRef.current) lastTickRef.current = now;
      const dt = (now - lastTickRef.current) / 1000;
      lastTickRef.current = now;
      setTime((t) => {
        const next = t + dt * rate;
        if (next >= total) { setPlaying(false); return total; }
        return next;
      });
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => { cancelAnimationFrame(rafRef.current); lastTickRef.current = 0; };
  }, [playing, rate, total]);

  // Active segment & word
  const activeSegment = useMemo(() => {
    for (let i = 0; i < segments.length; i++) {
      if (time >= segments[i].start && time < segments[i].end + 0.25) return segments[i];
    }
    return segments[segments.length - 1];
  }, [time, segments]);

  const activeWordIdx = useMemo(() => {
    if (!activeSegment) return -1;
    const seg = activeSegment;
    const dur = Math.max(0.1, seg.end - seg.start);
    const wordCount = seg.text.split(/\s+/).filter(Boolean).length;
    const t = Math.max(0, Math.min(dur, time - seg.start));
    const idx = Math.floor((t / dur) * wordCount);
    return Math.min(wordCount - 1, Math.max(0, idx));
  }, [time, activeSegment]);

  const activeSlide = slides.find((sl) => sl.id === activeSegment?.slide_id);

  // ── Editor tab / right rail tab / slide rail mode
  const [tab, setTab] = useState(initialTab || "ai"); // ai | stt | discrepancies | audit
  const [rightTab, setRightTab] = useState("chat");
  const [slideRailMode, setSlideRailMode] = useState(() => {
    const v = localStorage.getItem("mic_slide_click_mode");
    return v === "filter" ? "filter" : "focus";
  });
  useEffect(() => { localStorage.setItem("mic_slide_click_mode", slideRailMode); }, [slideRailMode]);
  const [focusedSlideId, setFocusedSlideId] = useState(null);
  const [activeSlideCollapsed, setActiveSlideCollapsed] = useState(false);

  // Resizable column widths (left and right rails). Center is fluid (1fr).
  const [leftW, setLeftW]   = useState(() => parseInt(localStorage.getItem("mic_left_w"))  || 320);
  const [rightW, setRightW] = useState(() => parseInt(localStorage.getItem("mic_right_w")) || 360);
  useEffect(() => { localStorage.setItem("mic_left_w", String(leftW));   }, [leftW]);
  useEffect(() => { localStorage.setItem("mic_right_w", String(rightW)); }, [rightW]);

  const onResizeLeft = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX, startW = leftW;
    const onMove = (ev) => setLeftW(Math.max(120, startW + (ev.clientX - startX)));
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.classList.remove("is-col-resizing");
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    document.body.classList.add("is-col-resizing");
  }, [leftW]);

  const onResizeRight = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX, startW = rightW;
    const onMove = (ev) => setRightW(Math.max(120, startW - (ev.clientX - startX)));
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.classList.remove("is-col-resizing");
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    document.body.classList.add("is-col-resizing");
  }, [rightW]);

  const gridStyle = { gridTemplateColumns: `${leftW}px 6px minmax(0, 1fr) 6px ${rightW}px` };

  // ── Placement state for anchor items (chat + polls inline in transcript) ──
  // Each entry: id -> segment_id (placed) or null (unplaced)
  const initialPlacements = useMemo(() => {
    const m = {};
    MIC_DATA.CHAT.forEach((c) => { m[c.id] = c.placed ? c.anchor : null; });
    MIC_DATA.POLLS.forEach((p) => { m[p.id] = p.placed ? p.anchor : null; });
    return m;
  }, []);
  const [placements, setPlacements] = useState(initialPlacements);

  const anchorsBySegment = useMemo(() => {
    const m = new Map();
    MIC_DATA.CHAT.forEach((c) => {
      const segId = placements[c.id];
      if (!segId) return;
      if (!m.has(segId)) m.set(segId, []);
      m.get(segId).push({ ...c, kind: "chat" });
    });
    MIC_DATA.POLLS.forEach((p) => {
      const segId = placements[p.id];
      if (!segId) return;
      if (!m.has(segId)) m.set(segId, []);
      m.get(segId).push({ ...p, kind: "poll" });
    });
    // Sort each segment's anchors by their original .t time
    m.forEach((arr) => arr.sort((a, b) => a.t - b.t));
    return m;
  }, [placements]);

  const handleRemoveAnchor = (itemId) => {
    setPlacements((prev) => ({ ...prev, [itemId]: null }));
  };
  const handleDropOnSegment = (itemId, segId) => {
    setPlacements((prev) => ({ ...prev, [itemId]: segId }));
  };

  const onSlideClick = (slideId) => {
    setFocusedSlideId(slideId);
    if (slideRailMode === "focus") {
      const segs = segmentsBySlide.get(slideId);
      if (segs && segs.length) setTime(segs[0].start);
    }
  };
  const onJumpToSegment = (segId) => {
    const seg = segmentsById.get(segId);
    if (seg) setTime(seg.start);
  };

  // ── Tab counts
  const counts = useMemo(() => ({
    ai: segments.length,
    stt: segments.length,
    disc: MIC_DATA.DISCREPANCIES.filter((d) => d.status === "open" && d.meaningful).length,
    audit: MIC_DATA.CORRECTIONS.length,
  }), [segments]);

  // ── Scrubber click
  const onScrubClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    setTime(Math.max(0, Math.min(total, pct * total)));
  };

  // Flag-category counts (mirrors the real-app FLAGGED filter row)
  const flagCounts = useMemo(() => {
    const counts = { medication: 0, name: 0, number: 0, date: 0, terminology: 0, filler: 0, punctuation: 0, style: 0, other: 0, uncertain: 0, drift: 0, low_conf: 0 };
    segments.forEach((s) => {
      s.ai_flags.forEach((f) => {
        if (f.kind === "uncertain") counts.uncertain++;
        if (f.kind === "drift") counts.drift++;
        if (f.kind === "low_confidence") counts.low_conf++;
      });
    });
    MIC_DATA.DISCREPANCIES.forEach((d) => {
      if (d.kind === "drift") counts.drift++;
      if (d.kind === "punctuation") counts.punctuation++;
      if (d.kind === "filler") counts.filler++;
      if (d.kind === "low_confidence") counts.low_conf++;
    });
    // Domain-specific picks from the surgical content
    counts.medication = 4;
    counts.terminology = 12;
    counts.name = 2;
    counts.number = 2;
    return counts;
  }, [segments]);
  const [flagFilter, setFlagFilter] = useState(null);

  return (
    <div className="editor" data-screen-label={`Editor / ${session.id}`}>
      <div className="editor__topbar">
        <div className="page-eyebrow" style={{ marginBottom: 6 }}>
          <Link to="/sessions">Sessions</Link><span className="sep">/</span>
          <Link to={`/s/${session.id}`}><code style={{ fontFamily: "var(--font-mono)", color: "var(--fg-link)" }}>{session.code || session.id}</code></Link><span className="sep">/</span>
          <span>Editor</span>
        </div>
        {/* Mini-stepper across the top */}
        <div className="editor__stepper" role="navigation" aria-label="SOP stages">
          {MIC_DATA.SOP_STAGES.map((st, i) => {
            const sessStageIdx = MIC_DATA.SOP_STAGES.findIndex((x) => x.id === session.stage);
            const isCurrent = st.id === session.stage;
            const isDone = i < sessStageIdx;
            return (
              <React.Fragment key={st.id}>
                <Link to={`/e/${session.id}/sop`} className={`editor__stepper-item ${isCurrent ? "is-current" : ""} ${isDone ? "is-done" : ""}`}>
                  <span className="dot" /> {st.name}
                </Link>
                {i < MIC_DATA.SOP_STAGES.length - 1 ? <span className="editor__stepper-sep">▸</span> : null}
              </React.Fragment>
            );
          })}
          <span style={{ marginLeft: "auto", fontSize: 10, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--color-green)" }}>
            <Icon name="check" size={11} /> AI ready
          </span>
        </div>

        {/* Big monospace title row */}
        <div className="editor__title-row">
          <h1 className="editor__title editor__title--mono">{session.code || session.id}</h1>
          <div className="page-actions">
            <button className="btn btn--ghost btn--sm" data-test-id="editor-result" title="Show last AI result" onClick={() => wired.toastInfo("Last AI result — opening side-by-side compare (mock)")}><Icon name="chevron-left" /> Result</button>
            <button className="btn btn--ghost btn--sm" data-test-id="editor-undo" title="Undo (⌘Z)" onClick={() => wired.toastInfo("Undone")}><Icon name="history" /> Undo</button>
            <button className="btn btn--ghost btn--sm" data-test-id="editor-redo" title="Redo (⇧⌘Z)" style={{ transform: "scaleX(-1)" }} onClick={() => wired.toastInfo("Redone")}><Icon name="history" /></button>
            <button className="btn btn--secondary btn--sm" data-test-id="editor-preview" title="Preview rendered output" onClick={() => navigate(`/v/${session.id}`)}><Icon name="external" /> Preview</button>
          </div>
        </div>

        {/* Sub-row: alignment status + tools */}
        <div className="editor__subrow">
          <span className="editor__align">
            <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "var(--color-green)" }}>{segments.length}/{segments.length}</span> aligned
          </span>
          <button className="btn btn--secondary btn--sm" data-test-id="editor-find-replace" onClick={wired.openFind}>
            <Icon name="search" /> Find &amp; Replace
          </button>
          <span style={{ marginLeft: "auto", display: "inline-flex", gap: 8, alignItems: "center" }}>
            <span className="stage-badge stage-badge--prep" style={{ textTransform: "uppercase" }}>{MIC_DATA.SOP_STAGES.find((x) => x.id === session.stage)?.name}</span>
            <Link to={`/e/${session.id}/sop`} className="btn btn--ghost btn--sm"><Icon name="branch" /> Workflow</Link>
            <Link to={`/e/${session.id}/audit`} className="btn btn--ghost btn--sm"><Icon name="history" /> Audit</Link>
            <DownloadMenu code={session.code || session.id} />
          </span>
        </div>

        {/* FLAGGED filter row */}
        <div className="editor__flagged">
          <span className="editor__flagged-label">Flagged:</span>
          {[
            { id: "medication",  label: "Medication",  color: "#C54644", n: flagCounts.medication },
            { id: "name",        label: "Name",        color: "#B9975B", n: flagCounts.name },
            { id: "number",      label: "Number",      color: "#B75D04", n: flagCounts.number },
            { id: "date",        label: "Date",        color: "#0861CE", n: 0 },
            { id: "terminology", label: "Terminology", color: "#7B1FA2", n: flagCounts.terminology },
            { id: "filler",      label: "Filler",      color: "#4D6995", n: flagCounts.filler },
            { id: "punctuation", label: "Punctuation", color: "#4D6995", n: flagCounts.punctuation },
            { id: "style",       label: "Style",       color: "#4D6995", n: 0 },
            { id: "other",       label: "Other",       color: "#4D6995", n: 0 },
          ].map((f) => (
            <button key={f.id} className={`editor__flag-chip ${f.n === 0 ? "is-empty" : ""} ${flagFilter === f.id ? "is-active" : ""}`}
              onClick={() => setFlagFilter(flagFilter === f.id ? null : f.id)}>
              <span className="dot" style={{ background: f.color }} /> {f.label} ({f.n})
            </button>
          ))}
          <span className="editor__flagged-divider" />
          {[
            { id: "uncertain",   label: "Uncertain",   n: flagCounts.uncertain },
            { id: "drift",       label: "Drift",       n: flagCounts.drift },
            { id: "low_conf",    label: "Low conf",    n: flagCounts.low_conf },
          ].map((f) => (
            <button key={f.id} className={`editor__flag-chip ${f.n === 0 ? "is-empty" : ""} ${flagFilter === f.id ? "is-active" : ""}`}
              onClick={() => setFlagFilter(flagFilter === f.id ? null : f.id)}>
              <span className="dot" /> {f.label} ({f.n})
            </button>
          ))}
        </div>
      </div>

      <div className="editor__tabs" role="tablist">
        <button className={`editor__tab ${tab === "ai" ? "is-active" : ""}`}        onClick={() => setTab("ai")}        role="tab"><Icon name="doc" /> AI Transcript <span className="count">{counts.ai}</span></button>
        <button className={`editor__tab ${tab === "stt" ? "is-active" : ""}`}       onClick={() => setTab("stt")}       role="tab"><Icon name="speaker" /> STT Reference <span className="count">{counts.stt}</span></button>
        <button className={`editor__tab ${tab === "disc" ? "is-active" : ""}`}      onClick={() => setTab("disc")}      role="tab"><Icon name="git" /> Discrepancies <span className="count">{counts.disc}</span></button>
        <button className={`editor__tab ${tab === "audit" ? "is-active" : ""}`}     onClick={() => setTab("audit")}     role="tab"><Icon name="history" /> Audit <span className="count">{counts.audit}</span></button>
        <div className="editor__tab-spacer" />
        <div className="editor__tab-meta">
          <FlagLegend />
        </div>
      </div>

      {tab === "ai" ? (
        <div className="editor__grid" style={gridStyle}>
          <aside className="editor__leftcol">
            <VideoStrip
              session={session}
              activeSlide={activeSlide}
              slides={slides}
              time={time}
              total={total}
              playing={playing}
              setPlaying={setPlaying}
              rate={rate}
              setRate={setRate}
              cc={cc}
              setCc={setCc}
              muted={muted}
              setMuted={setMuted}
              volume={volume}
              setVolume={setVolume}
              setTime={setTime}
              onScrubClick={onScrubClick}
              segmentsBySlide={segmentsBySlide}
            />
            <SlideRail
              slides={slides}
              activeSlideId={activeSlide?.id}
              focusedSlideId={focusedSlideId}
              mode={slideRailMode}
              onModeChange={(m) => { setSlideRailMode(m); setFocusedSlideId(null); }}
            onClearFocus={() => setFocusedSlideId(null)}
              onSlideClick={onSlideClick}
              segmentsBySlide={segmentsBySlide}
            />
          </aside>
          <div className="editor__resizer" onMouseDown={onResizeLeft} title="Drag to resize" />
          <TranscriptPane
            segments={segments}
            activeSegmentId={activeSegment?.id}
            activeWordIdx={activeWordIdx}
            focusedSlideId={focusedSlideId}
            slideRailMode={slideRailMode}
            anchorsBySegment={anchorsBySegment}
            onRemoveAnchor={handleRemoveAnchor}
            onDropOnSegment={handleDropOnSegment}
            onJumpToSegment={onJumpToSegment}
            onSegmentClick={(segId) => { const s = segmentsById.get(segId); if (s) setTime(s.start); }}
            onWordClick={(segId, w) => {
              const s = segmentsById.get(segId);
              if (!s) return;
              const dur = s.end - s.start;
              const wordCount = s.text.split(/\s+/).filter(Boolean).length;
              setTime(s.start + (w / wordCount) * dur);
            }}
            onClearFocus={() => setFocusedSlideId(null)}
          />
          <div className="editor__resizer" onMouseDown={onResizeRight} title="Drag to resize" />
          <aside className="rightrail" aria-label="Side panel" data-screen-label="Right Rail">
            <ActiveSlideCard
              slide={activeSlide}
              segmentCount={segmentsBySlide.get(activeSlide?.id || "")?.length || 0}
              collapsed={activeSlideCollapsed}
              onToggle={() => setActiveSlideCollapsed((c) => !c)}
              time={time}
              totalDuration={total}
            />
            <div className="rightrail__tabs" role="tablist">
              <button className={`rightrail__tab ${rightTab === "admin" ? "is-active" : ""}`} onClick={() => setRightTab("admin")} role="tab"><Icon name="user" /> Admin</button>
              <button className={`rightrail__tab ${rightTab === "chat" ? "is-active" : ""}`}  onClick={() => setRightTab("chat")}  role="tab"><Icon name="message" /> Chat <span className="count">{MIC_DATA.CHAT.length}</span></button>
              <button className={`rightrail__tab ${rightTab === "polls" ? "is-active" : ""}`} onClick={() => setRightTab("polls")} role="tab"><Icon name="list" /> Polls <span className="count">{MIC_DATA.POLLS.length}</span></button>
            </div>
            <div className="rightrail__panel">
              {rightTab === "admin" && <AdminTab slide={activeSlide} segments={segments} time={time} totalDuration={total} slides={slides} />}
              {rightTab === "chat"  && <ChatTab  chat={MIC_DATA.CHAT}  slides={slides} segmentsById={segmentsById} onJumpToSegment={onJumpToSegment} placements={placements} onUnplace={handleRemoveAnchor} onPlaceAtActive={(id) => activeSegment && handleDropOnSegment(id, activeSegment.id)} />}
              {rightTab === "polls" && <PollsTab polls={MIC_DATA.POLLS} segmentsById={segmentsById} onJumpToSegment={onJumpToSegment} placements={placements} onUnplace={handleRemoveAnchor} onPlaceAtActive={(id) => activeSegment && handleDropOnSegment(id, activeSegment.id)} />}
            </div>
          </aside>
        </div>
      ) : null}

      {tab === "stt" ? (
        <div className="editor__grid" style={gridStyle}>
          <aside className="editor__leftcol">
            <VideoStrip
              session={session}
              activeSlide={activeSlide}
              slides={slides}
              time={time}
              total={total}
              playing={playing}
              setPlaying={setPlaying}
              rate={rate}
              setRate={setRate}
              cc={cc}
              setCc={setCc}
              muted={muted}
              setMuted={setMuted}
              volume={volume}
              setVolume={setVolume}
              setTime={setTime}
              onScrubClick={onScrubClick}
              segmentsBySlide={segmentsBySlide}
            />
            <SlideRail
              slides={slides}
              activeSlideId={activeSlide?.id}
              focusedSlideId={focusedSlideId}
              mode={slideRailMode}
              onModeChange={(m) => { setSlideRailMode(m); setFocusedSlideId(null); }}
            onClearFocus={() => setFocusedSlideId(null)}
              onSlideClick={onSlideClick}
              segmentsBySlide={segmentsBySlide}
            />
          </aside>
          <div className="editor__resizer" onMouseDown={onResizeLeft} title="Drag to resize" />
          <STTPane
            segments={segments}
            activeSegmentId={activeSegment?.id}
            activeWordIdx={activeWordIdx}
            time={time}
            focusedSlideId={focusedSlideId}
            slideRailMode={slideRailMode}
            onClearFocus={() => setFocusedSlideId(null)}
            onSegmentClick={(segId) => { const s = segmentsById.get(segId); if (s) setTime(s.start); }}
            onWordClick={(segId, w) => {
              const s = segmentsById.get(segId);
              if (!s) return;
              const dur = s.end - s.start;
              const wordCount = s.text.split(/\s+/).filter(Boolean).length;
              setTime(s.start + (w / wordCount) * dur);
            }}
          />
          <div className="editor__resizer" onMouseDown={onResizeRight} title="Drag to resize" />
          <STTSidePanel time={time} totalDuration={total} segments={segments} />
        </div>
      ) : null}

      {tab === "disc" ? (
        <div className="editor__grid" style={gridStyle}>
          <aside className="editor__leftcol">
            <VideoStrip
              session={session}
              activeSlide={activeSlide}
              slides={slides}
              time={time}
              total={total}
              playing={playing}
              setPlaying={setPlaying}
              rate={rate}
              setRate={setRate}
              cc={cc}
              setCc={setCc}
              muted={muted}
              setMuted={setMuted}
              volume={volume}
              setVolume={setVolume}
              setTime={setTime}
              onScrubClick={onScrubClick}
              segmentsBySlide={segmentsBySlide}
            />
            <SlideRail
              slides={slides}
              activeSlideId={activeSlide?.id}
              focusedSlideId={focusedSlideId}
              mode={slideRailMode}
              onModeChange={(m) => { setSlideRailMode(m); setFocusedSlideId(null); }}
            onClearFocus={() => setFocusedSlideId(null)}
              onSlideClick={onSlideClick}
              segmentsBySlide={segmentsBySlide}
            />
          </aside>
          <div className="editor__resizer" onMouseDown={onResizeLeft} title="Drag to resize" />
          <DiscrepanciesPane activeSegmentId={activeSegment?.id} onSegmentClick={(segId) => { const s = segmentsById.get(segId); if (s) setTime(s.start); }} focusedSlideId={focusedSlideId} slideRailMode={slideRailMode} onClearFocus={() => setFocusedSlideId(null)} />
          <div className="editor__resizer" onMouseDown={onResizeRight} title="Drag to resize" />
          <aside className="rightrail" aria-label="Side panel" data-screen-label="Right Rail">
            <ActiveSlideCard
              slide={activeSlide}
              segmentCount={segmentsBySlide.get(activeSlide?.id || "")?.length || 0}
              collapsed={activeSlideCollapsed}
              onToggle={() => setActiveSlideCollapsed((c) => !c)}
              time={time}
              totalDuration={total}
            />
            <div className="rightrail__tabs" role="tablist">
              <button className={`rightrail__tab ${rightTab === "admin" ? "is-active" : ""}`} onClick={() => setRightTab("admin")} role="tab"><Icon name="user" /> Admin</button>
              <button className={`rightrail__tab ${rightTab === "chat" ? "is-active" : ""}`}  onClick={() => setRightTab("chat")}  role="tab"><Icon name="message" /> Chat <span className="count">{MIC_DATA.CHAT.length}</span></button>
              <button className={`rightrail__tab ${rightTab === "polls" ? "is-active" : ""}`} onClick={() => setRightTab("polls")} role="tab"><Icon name="list" /> Polls <span className="count">{MIC_DATA.POLLS.length}</span></button>
            </div>
            <div className="rightrail__panel">
              {rightTab === "admin" && <AdminTab slide={activeSlide} segments={segments} time={time} totalDuration={total} slides={slides} />}
              {rightTab === "chat"  && <ChatTab  chat={MIC_DATA.CHAT}  slides={slides} segmentsById={segmentsById} onJumpToSegment={onJumpToSegment} placements={placements} onUnplace={handleRemoveAnchor} onPlaceAtActive={(id) => activeSegment && handleDropOnSegment(id, activeSegment.id)} />}
              {rightTab === "polls" && <PollsTab polls={MIC_DATA.POLLS} segmentsById={segmentsById} onJumpToSegment={onJumpToSegment} placements={placements} onUnplace={handleRemoveAnchor} onPlaceAtActive={(id) => activeSegment && handleDropOnSegment(id, activeSegment.id)} />}
            </div>
          </aside>
        </div>
      ) : null}
      {tab === "audit" ? (
        <div className="editor__grid" style={gridStyle}>
          <aside className="editor__leftcol">
            <VideoStrip
              session={session}
              activeSlide={activeSlide}
              slides={slides}
              time={time}
              total={total}
              playing={playing}
              setPlaying={setPlaying}
              rate={rate}
              setRate={setRate}
              cc={cc}
              setCc={setCc}
              muted={muted}
              setMuted={setMuted}
              volume={volume}
              setVolume={setVolume}
              setTime={setTime}
              onScrubClick={onScrubClick}
              segmentsBySlide={segmentsBySlide}
            />
            <SlideRail
              slides={slides}
              activeSlideId={activeSlide?.id}
              focusedSlideId={focusedSlideId}
              mode={slideRailMode}
              onModeChange={(m) => { setSlideRailMode(m); setFocusedSlideId(null); }}
            onClearFocus={() => setFocusedSlideId(null)}
              onSlideClick={onSlideClick}
              segmentsBySlide={segmentsBySlide}
            />
          </aside>
          <div className="editor__resizer" onMouseDown={onResizeLeft} title="Drag to resize" />
          <AuditTabInline session={session} activeSegmentId={activeSegment?.id} onSegmentClick={(segId) => { const s = segmentsById.get(segId); if (s) setTime(s.start); }} />
          <div className="editor__resizer" onMouseDown={onResizeRight} title="Drag to resize" />
          <aside className="rightrail" aria-label="Side panel" data-screen-label="Right Rail">
            <ActiveSlideCard
              slide={activeSlide}
              segmentCount={segmentsBySlide.get(activeSlide?.id || "")?.length || 0}
              collapsed={activeSlideCollapsed}
              onToggle={() => setActiveSlideCollapsed((c) => !c)}
              time={time}
              totalDuration={total}
            />
            <div className="rightrail__tabs" role="tablist">
              <button className={`rightrail__tab ${rightTab === "admin" ? "is-active" : ""}`} onClick={() => setRightTab("admin")} role="tab"><Icon name="user" /> Admin</button>
              <button className={`rightrail__tab ${rightTab === "chat" ? "is-active" : ""}`}  onClick={() => setRightTab("chat")}  role="tab"><Icon name="message" /> Chat <span className="count">{MIC_DATA.CHAT.length}</span></button>
              <button className={`rightrail__tab ${rightTab === "polls" ? "is-active" : ""}`} onClick={() => setRightTab("polls")} role="tab"><Icon name="list" /> Polls <span className="count">{MIC_DATA.POLLS.length}</span></button>
            </div>
            <div className="rightrail__panel">
              {rightTab === "admin" && <AdminTab slide={activeSlide} segments={segments} time={time} totalDuration={total} slides={slides} />}
              {rightTab === "chat"  && <ChatTab  chat={MIC_DATA.CHAT}  slides={slides} segmentsById={segmentsById} onJumpToSegment={onJumpToSegment} placements={placements} onUnplace={handleRemoveAnchor} onPlaceAtActive={(id) => activeSegment && handleDropOnSegment(id, activeSegment.id)} />}
              {rightTab === "polls" && <PollsTab polls={MIC_DATA.POLLS} segmentsById={segmentsById} onJumpToSegment={onJumpToSegment} placements={placements} onUnplace={handleRemoveAnchor} onPlaceAtActive={(id) => activeSegment && handleDropOnSegment(id, activeSegment.id)} />}
            </div>
          </aside>
        </div>
      ) : null}

      <div className="editor__statusbar">
        <span className="dot" /> WS connected · 18ms
        <span className="sep" />
        <span>autosave <code>2s ago</code></span>
        <span className="sep" />
        <span>longtasks/min: <code style={{ color: "#5BE3A4" }}>1</code></span>
        <span className="sep" />
        <span>heap: <code>108 MB · flat over 30m</code></span>
        <span className="end">
          <span>shortcut: <code>?</code></span>
          <span className="sep" />
          <span>build <code>v4.0.0-ssot-r2</code></span>
        </span>
      </div>
    </div>
  );
}

window.EditorRoute = EditorRoute;
window.SlideRail = SlideRail;
window.TranscriptPane = TranscriptPane;
window.ActiveSlideCard = ActiveSlideCard;
