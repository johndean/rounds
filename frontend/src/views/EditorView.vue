<script setup lang="ts">
/**
 * EditorView — same DOM as React editor.jsx::EditorRoute.
 *
 * Wired to the live backend:
 *   GET /v1/sessions/{id}              — session shell
 *   GET /v1/sessions/{id}/segments     — AI transcript segments
 *   GET /v1/sessions/{id}/slides       — slide deck
 *   GET /v1/sessions/{id}/chat         — chat anchors
 *   GET /v1/sessions/{id}/polls        — poll anchors
 *   GET /v1/sessions/{id}/discrepancies — STT-vs-base diffs
 *   GET /v1/audit/sessions/{id}/corrections — append-only ledger
 *
 * Empty state until the ingest pipeline (Phase 6) produces rows. The 3-column
 * layout, slide rail, transcript pane, STT pane, discrepancies pane, audit
 * pane, and right-rail tabs all render their empty-state copy gracefully.
 *
 * Critical invariants:
 *   - React JSX at docs/port-source/editor.jsx is the SINGLE SOURCE OF TRUTH
 *     for layout / class names / data-test-ids. Do not edit the Vue template
 *     to "improve" structure — diverging from the JSX is a regression.
 *   - Every edit becomes an append-only corrections row (ADR-005). Undo/redo
 *     are pointer moves, never row deletions.
 *
 * Related ADRs: ADR-005 (corrections ledger), ADR-009 (editor architecture),
 * ADR-008 (WebSocket — receives correction events from other tabs + worker),
 * ADR-010 (hash-routed SPA).
 * Related business rules: BR-001 (Admin tab gate), BR-006 (discrepancy
 * priority order), BR-018 (Mark OK auto-closes discrepancies).
 */
import { ref, computed, watch, onMounted, onUnmounted, provide } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import Icon from '@/components/shared/Icon.vue';
import FlagLegend from '@/components/editor/FlagLegend.vue';
import VideoStrip from '@/components/editor/VideoStrip.vue';
import SlideRail from '@/components/editor/SlideRail.vue';
import TranscriptPane from '@/components/editor/TranscriptPane.vue';
import STTPane from '@/components/editor/STTPane.vue';
import STTSidePanel from '@/components/editor/STTSidePanel.vue';
import DiscrepanciesPane from '@/components/editor/DiscrepanciesPane.vue';
import AuditTabInline from '@/components/editor/AuditTabInline.vue';
import ActiveSlideCard from '@/components/editor/ActiveSlideCard.vue';
import AdminTab from '@/components/editor/AdminTab.vue';
import SpeakerEditPanel from '@/components/editor/SpeakerEditPanel.vue';
import ChatTab from '@/components/editor/ChatTab.vue';
import PollsTab from '@/components/editor/PollsTab.vue';
import DownloadMenu from '@/components/editor/DownloadMenu.vue';
import EditorSkeleton from '@/components/shared/EditorSkeleton.vue';
import { useSessionLock } from '@/composables/useSessionLock';
import { useIsAdmin } from '@/composables/useIsAdmin';
import { useAutosave, AUTOSAVE_STATUS_KEY } from '@/composables/useAutosave';
import { sessions as sessionsApi, segments as segmentsApi, audit as auditApi, corrections as correctionsApi, speakers as speakersApi, words as wordsApi, discrepancies as discrepanciesApi, wordAlignment as wordAlignmentApi, media as mediaApi, placements as placementsApi, type SessionSummary, type WordRow, type DiscrepancyRow, type WordAlignmentEntry } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';
import { http } from '@/services/http';
import type { Segment, Slide } from '@/fixtures/transcript';
import type { ChatMessage, Poll } from '@/fixtures/chat_polls';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { modal } from '@/composables/useModal';
import FindReplaceModal from '@/components/overlays/FindReplaceModal.vue';
import { useSyncController } from '@/composables/useSyncController';
import { useWsSubscriber } from '@/composables/useWsSubscriber';

const bundleSha = ((import.meta as unknown as { env: { VITE_BUILD_SHA?: string } }).env.VITE_BUILD_SHA || 'dev');
const bundleShort = bundleSha === 'dev' ? 'dev' : bundleSha.slice(0, 7);

type TabId = 'ai' | 'stt' | 'disc' | 'audit';
type RightTabId = 'admin' | 'chat' | 'polls';

const props = defineProps<{ id: string; initialTab?: TabId }>();
const router = useRouter();

// Phase 1 (2026-06-05): concurrent-edit lock. Banner renders read-only state
// when another operator holds the session. Phase 2's autosave gates its
// writes on `isHolder.value === true` (fail-closed when null or false).
const { isHolder, holder, lockError, forceTake } = useSessionLock(props.id);
const isAdmin = useIsAdmin();
const isReadOnly = computed(() => isHolder.value !== true);

// Phase 2 (2026-06-05): debounced autosave gated by the Phase 1 lock.
// Per-segment status is provided to TranscriptPane / SegmentText via
// inject(AUTOSAVE_STATUS_KEY) so children can render their own badge
// without reactive thrash on the 600-segment v-for.
const autosave = useAutosave(props.id, isHolder);
provide(AUTOSAVE_STATUS_KEY, autosave.status);

// ── Data refs (empty until backend populates) ─────────────────────────
const session = ref<SessionSummary | null>(null);
const SLIDES = ref<Slide[]>([]);
const SEGMENTS = ref<Segment[]>([]);
interface ApiSpeaker { id: string; short: string | null; name: string | null; role: string | null; avatar_color: string | null }
const SPEAKERS_API = ref<ApiSpeaker[]>([]);
const CHAT = ref<ChatMessage[]>([]);
const POLLS = ref<Poll[]>([]);
const DISCREPANCIES = ref<DiscrepancyRow[]>([]);
const CORRECTIONS = ref<Array<{ id: string; t: string; type: string; actor: string; seg: string; prior?: string | null; next?: string | null; note?: string | null }>>([]);
// Real Google STT per-word data grouped by segment_id. Populated by
// stt_background_task after AI MODE direct. Empty until the worker writes
// the words rows + emits stt_ready over WS.
const WORDS_BY_SEGMENT = ref<Map<string, WordRow[]>>(new Map());
// L2 word-highlight alignment grouped by segment_id. Every Gemini word in a
// segment gets one entry (matched STT word → real timestamps; unmatched →
// nulls). The AI Transcript tab uses this to anchor karaoke highlight to
// real audio timing instead of MIC's drifting proportional interpolation.
// Empty Map for legacy sessions uploaded before migration 036 — TranscriptPane
// falls through to a no-highlight render path in that case.
const ALIGNMENT_BY_SEGMENT = ref<Map<string, WordAlignmentEntry[]>>(new Map());
// Pipeline config — drives the AI-mode badge in the topbar so a tester can
// see at a glance whether segments.text came from Gemini direct vs.
// transcribe+normalize (enhanced). Null while loading or for legacy sessions.
const pipelineCfg = ref<{ ai_pipeline: string; ai_mode: string; ai_model: string } | null>(null);
const loading = ref(true);

// Phase A7 — per-stage loading progress. Each stage is independently
// observable so a slow / failed dependency doesn't hide the rest of the
// load behind a generic spinner. Stages flip 'pending' → 'done' | 'error'
// as their fetch settles; the strip renders only while `loading` is true
// and the helper below wraps each fetch in a track() that returns the
// fallback on rejection (preserves the existing .catch(() => []) semantics).
type LoadStageState = 'pending' | 'done' | 'error';
type LoadStageKey = 'session' | 'segments' | 'slides' | 'speakers'
  | 'chat' | 'polls' | 'discrepancies' | 'corrections' | 'words' | 'pipeline' | 'alignment';
const _initialStages = (): Record<LoadStageKey, LoadStageState> => ({
  session: 'pending', segments: 'pending', slides: 'pending', speakers: 'pending',
  chat: 'pending', polls: 'pending', discrepancies: 'pending', corrections: 'pending',
  words: 'pending', pipeline: 'pending', alignment: 'pending',
});
const loadStages = ref<Record<LoadStageKey, LoadStageState>>(_initialStages());
const LOAD_STAGE_LABELS: Record<LoadStageKey, string> = {
  session: 'Session', segments: 'Segments', slides: 'Slides', speakers: 'Speakers',
  chat: 'Chat', polls: 'Polls', discrepancies: 'Discrepancies', corrections: 'Audit',
  words: 'Words', pipeline: 'Pipeline', alignment: 'Alignment',
};
function _trackLoad<T>(stage: LoadStageKey, p: Promise<T>, fallback: T): Promise<T> {
  return p
    .then((r) => { loadStages.value[stage] = 'done'; return r; })
    .catch(() => { loadStages.value[stage] = 'error'; return fallback; });
}
const loadProgressPct = computed(() => {
  const states = Object.values(loadStages.value);
  const settled = states.filter((s) => s !== 'pending').length;
  return Math.round((settled / states.length) * 100);
});
const loadHasError = computed(() => Object.values(loadStages.value).some((s) => s === 'error'));

const TOTAL_DURATION = ref<number>(0);
const mediaUrl = ref<string | null>(null);
const mediaKind = ref<'video' | 'audio' | null>(null);
const sessionCode = computed(() => session.value?.code || props.id);
const sessionStage = computed(() => 'prep'); // until /sop wiring lands per-editor

async function load(opts: { silent?: boolean } = {}): Promise<void> {
  if (!opts.silent) {
    loading.value = true;
    loadStages.value = _initialStages();
  }
  try {
    // Each fetch is wrapped in _trackLoad so its stage state flips
    // 'pending' → 'done' on resolve, → 'error' on reject (with the
    // fallback preserved so existing call-site assumptions hold).
    const [s, sg, sl, sp, ch, po, di, co, wd, pc, al] = await Promise.all([
      _trackLoad('session',       sessionsApi.get(props.id),                                                                     null),
      _trackLoad('segments',      segmentsApi.list(props.id),                                                                    [] as Array<{ id: string; seq: number; start_ms: number; end_ms: number; text: string; confidence: number | null; flags: string[]; slide_id: string | null; speaker_id: string | null }>),
      _trackLoad('slides',        http<Array<{ id: string; slide_index: number; title: string | null }>>(`/v1/sessions/${encodeURIComponent(props.id)}/slides`), [] as Array<{ id: string; slide_index: number; title: string | null }>),
      _trackLoad('speakers',      http<ApiSpeaker[]>(`/v1/sessions/${encodeURIComponent(props.id)}/speakers`),                   [] as ApiSpeaker[]),
      _trackLoad('chat',          http<ChatMessage[]>(`/v1/sessions/${encodeURIComponent(props.id)}/chat`),                      [] as ChatMessage[]),
      _trackLoad('polls',         http<Poll[]>(`/v1/sessions/${encodeURIComponent(props.id)}/polls`),                            [] as Poll[]),
      _trackLoad('discrepancies', discrepanciesApi.list(props.id),                                                               { session_id: props.id, count: 0, classified_count: 0, classification_status: 'pending' as const, discrepancies: [] as DiscrepancyRow[] }),
      _trackLoad('corrections',   auditApi.corrections(props.id),                                                                [] as Array<{ id: string; segment_id: string; correction_type: string; created_at: string; created_by: string; old_text: string; new_text: string }>),
      _trackLoad('words',         wordsApi.listBySession(props.id),                                                              [] as WordRow[]),
      _trackLoad('pipeline',      sessionsApi.pipelineConfig(props.id),                                                          null),
      _trackLoad('alignment',     wordAlignmentApi.get(props.id),                                                                { session_id: props.id, count: 0, matched: 0, segments: {} as Record<string, WordAlignmentEntry[]> }),
    ]);
    session.value = s;
    pipelineCfg.value = pc;
    if (s?.duration_sec) TOTAL_DURATION.value = s.duration_sec;
    // Fetch playback URL in parallel; failure is non-fatal (poster + scrubber stay static).
    // Request video first — backend's ORDER BY (role = :preferred) DESC falls through
    // to audio for sessions that don't have a video source.
    void mediaApi.url(props.id, 'video')
      .then((m) => {
        mediaUrl.value = m.url;
        mediaKind.value = (m.content_type || '').startsWith('video/') ? 'video' : 'audio';
        if (m.duration_sec && TOTAL_DURATION.value <= 0) TOTAL_DURATION.value = m.duration_sec;
      })
      .catch(() => { mediaUrl.value = null; mediaKind.value = null; });
    SPEAKERS_API.value = sp as ApiSpeaker[];
    const speakersById = new Map<string, ApiSpeaker>();
    SPEAKERS_API.value.forEach((row) => speakersById.set(row.id, row));
    // Map API segment shape → editor Segment shape. Real speaker name + color
    // are embedded so TranscriptPane/DiscrepanciesPane can render the real
    // roster via speakerDisplay(seg) without fixture fallback. The legacy
    // fixture key (`speaker: 'presenter'`) stays for backward-compat with any
    // code that still keys off it.
    SEGMENTS.value = (sg as Array<{ id: string; seq: number; start_ms: number; end_ms: number; text: string; confidence: number | null; flags: string[]; slide_id: string | null; speaker_id: string | null }>).map((row, i): Segment => {
      const sp = row.speaker_id ? speakersById.get(row.speaker_id) : undefined;
      return {
        id: row.id,
        idx: typeof row.seq === 'number' ? row.seq : i,
        start: (row.start_ms ?? 0) / 1000,
        end: (row.end_ms ?? 0) / 1000,
        speaker: 'presenter',
        slide_id: row.slide_id,
        text: row.text || '',
        ai_flags: (row.flags || []).map((kind) => ({ w: 0, kind: kind as 'drift' | 'uncertain' | 'low_confidence' })),
        needs_review: (row.flags || []).length > 0,
        has_user_override: false,
        confidence: typeof row.confidence === 'number' && row.confidence < 0.75 ? 'low' : 'normal',
        corrections: [],
        speaker_id: row.speaker_id ?? null,
        speaker_name: sp?.name ?? null,
        speaker_short: sp?.short ?? null,
        speaker_role: sp?.role ?? null,
        speaker_color: sp?.avatar_color ?? null,
      };
    });
    SLIDES.value = (sl as Array<{ id: string; slide_index: number; title: string | null }>).map((row): Slide => ({
      id: row.id,
      n: row.slide_index + 1,
      title: row.title || '',
      kind: 'data',
    }));
    // Adapt backend chat shape (anchor_segment, sent_at_ms, body) → editor
    // ChatMessage shape (anchor, t, text) so ChatTab can render real DB rows
    // using the same template as the fixture demo.
    interface ApiChat { id: string; author: string; body: string; sent_at_ms: number; anchor_segment: string | null; placed: boolean }
    CHAT.value = (ch as unknown as ApiChat[]).map((c): ChatMessage => ({
      id:     c.id,
      author: c.author,
      anchor: c.anchor_segment || '',
      t:      (c.sent_at_ms ?? 0) / 1000,
      text:   c.body,
      placed: c.placed,
    }));

    // Adapt backend poll shape (total_votes, anchor_segment, opened_at_ms,
    // options[{seq, votes, label}]) → editor Poll shape (total, anchor, t,
    // options[{id, label, votes}]). Backend's `metadata.slide_n` is also
    // surfaced so we can auto-place polls onto the first segment of that
    // slide (Bug 2 — MIC's polls land on their declared slide; Rounds
    // wasn't doing that on its own).
    interface ApiPollOption { id: string; label: string; seq: number; votes: number }
    interface ApiPoll {
      id: string; question: string; status: 'open' | 'closed';
      opened_at_ms: number; closed_at_ms: number | null;
      total_votes: number; anchor_segment: string | null; placed: boolean;
      options: ApiPollOption[]; metadata?: { slide_n?: number };
    }
    const slidesByIndex = new Map<number, string>();
    SLIDES.value.forEach((sl) => slidesByIndex.set(sl.n, sl.id));
    const firstSegBySlide = new Map<string, string>();
    SEGMENTS.value.forEach((seg) => {
      if (seg.slide_id && !firstSegBySlide.has(seg.slide_id)) {
        firstSegBySlide.set(seg.slide_id, seg.id);
      }
    });
    function _inferAnchor(p: ApiPoll): string {
      if (p.anchor_segment) return p.anchor_segment;
      const slideN = p.metadata?.slide_n;
      if (typeof slideN === 'number') {
        const slideId = slidesByIndex.get(slideN);
        if (slideId) {
          const segId = firstSegBySlide.get(slideId);
          if (segId) return segId;
        }
      }
      return '';
    }
    POLLS.value = (po as unknown as ApiPoll[]).map((p): Poll => ({
      id:       p.id,
      anchor:   _inferAnchor(p),
      t:        (p.opened_at_ms ?? 0) / 1000,
      placed:   p.placed || !!_inferAnchor(p),
      question: p.question,
      options:  (p.options || []).map((o) => ({ id: o.id, label: o.label, votes: o.votes })),
      total:    p.total_votes ?? 0,
      status:   p.status,
    }));
    // Pre-populate the placement map so anchored chat/polls render in their
    // segment positions on first load (otherwise placements is empty and
    // anchorsBySegment shows nothing).
    const initialPlacements: Record<string, string | null> = {};
    CHAT.value.forEach((c) => { if (c.anchor) initialPlacements[c.id] = c.anchor; });
    POLLS.value.forEach((p) => { if (p.anchor) initialPlacements[p.id] = p.anchor; });
    placements.value = { ...placements.value, ...initialPlacements };

    // di is the new envelope {session_id, count, classification_status, classified_count, discrepancies}.
    // Store the inner array; the envelope's totals are derivable from .length.
    DISCREPANCIES.value = (di as { discrepancies?: DiscrepancyRow[] }).discrepancies ?? [];
    CORRECTIONS.value = co as Array<{ id: string; t: string; type: string; actor: string; seg: string; prior?: string | null; next?: string | null; note?: string | null }>;

    // Group real Google STT words by segment_id so STTPane can render real
    // per-word tokens with real timestamps + confidences. Empty Map when
    // stt_background hasn't completed yet — STTPane shows its placeholder.
    const wordsMap = new Map<string, WordRow[]>();
    (wd as WordRow[]).forEach((w) => {
      const arr = wordsMap.get(w.segment_id);
      if (arr) arr.push(w);
      else wordsMap.set(w.segment_id, [w]);
    });
    WORDS_BY_SEGMENT.value = wordsMap;

    // L2 word alignment: convert the {segments: {seg_id: [entries…]}} envelope
    // to a Map keyed by segment_id. Each segment_id maps to a positional array
    // where index N is the alignment for the Nth Gemini word (seg.text.split()).
    const alignmentMap = new Map<string, WordAlignmentEntry[]>();
    const alSegments = (al as { segments?: Record<string, WordAlignmentEntry[]> }).segments || {};
    Object.entries(alSegments).forEach(([segId, entries]) => {
      alignmentMap.set(segId, entries);
    });
    ALIGNMENT_BY_SEGMENT.value = alignmentMap;
  } finally {
    if (!opts.silent) loading.value = false;
  }
}
// WS sync — listens for stt_ready / stt_failed / discrepancies_ready while
// the editor is open. Mirrors MIC's pattern: AI MODE direct completes first
// and transitions to ready; STT runs in the background. The STT Raw tab
// shows "processing in background" until sttReady flips to true.
const {
  sttReady, sttFailed,
  connect: wsConnect, disconnect: wsDisconnect,
} = useSyncController(props.id);

// Live remote-change subscribers — share the same pooled connection as
// useSyncController above. Refresh segments + audit + discrepancies when
// another tab (or our own backend echo) reports a change. Coalesces bursts
// (e.g. find/replace fans out many correction_applied events) into a single
// quiet refetch via debounce.
let _wsRefreshTimer: ReturnType<typeof setTimeout> | null = null;
function scheduleQuietRefresh(): void {
  if (_wsRefreshTimer) clearTimeout(_wsRefreshTimer);
  _wsRefreshTimer = setTimeout(() => {
    _wsRefreshTimer = null;
    void load({ silent: true });
  }, 250);
}
useWsSubscriber(props.id, {
  correction_applied:   scheduleQuietRefresh,
  discrepancy_resolved: scheduleQuietRefresh,
  timeline_ready:       () => { void load(); },
  // classify_discrepancies_task runs in the background after a session goes
  // ready. Each step refreshes discrepancies so DiscrepanciesPane's
  // "Meaningful" count updates without a manual reload.
  classification_complete: scheduleQuietRefresh,
  classification_partial:  scheduleQuietRefresh,
  // Late events can arrive minutes after the editor closes and resurface
  // on the next visit, so `info` + "Background:" prefix signals this is
  // not actionable from this view. Truncate reason — backend payload is
  // raw str(exc) which can be long Celery wrappers.
  classification_failed: (msg) => {
    const raw = typeof msg.reason === 'string' ? msg.reason : 'unknown';
    const reason = raw.length > 80 ? raw.slice(0, 77) + '…' : raw;
    toast.push(`Background: discrepancy classification failed — ${reason}`, { tone: 'info' });
  },
});

onMounted(() => { void load(); wsConnect(); });
onUnmounted(() => {
  if (_wsRefreshTimer) { clearTimeout(_wsRefreshTimer); _wsRefreshTimer = null; }
  wsDisconnect();
});

// Promote sttReady true as soon as we have any segments. The segments
// endpoint doesn't return per-word arrays (those live in the words table),
// so the old `hasWords` check never fired and the STT tab stayed stuck on
// the "Speech-to-text processing in background" spinner forever. While the
// STT pane is technically rendering an AI-transcript-mirror placeholder
// today, the right gate is "do we have anything to show" (= segments exist),
// not "are there word-level arrays on the segment objects."
watch(SEGMENTS, (segs) => {
  if (sttReady.value) return;
  if (segs.length > 0) sttReady.value = true;
}, { immediate: true });

// ── Derived maps + computeds ─────────────────────────────────────────
const segmentsById = computed<Map<string, Segment>>(() => {
  const m = new Map<string, Segment>();
  SEGMENTS.value.forEach((s) => m.set(s.id, s));
  return m;
});
const segmentsBySlide = computed<Map<string, Segment[]>>(() => {
  const m = new Map<string, Segment[]>();
  SLIDES.value.forEach((sl) => m.set(sl.id, []));
  SEGMENTS.value.forEach((s) => { if (s.slide_id) m.get(s.slide_id)?.push(s); });
  return m;
});

const time = ref<number>((() => {
  const v = parseFloat(localStorage.getItem(`mic_playback_${props.id}`) ?? '');
  return isNaN(v) ? 0 : v;
})());
const playing = ref(false);
const rate = ref(1);
const cc = ref(true);

// Playback is driven by the <audio> element inside VideoStrip via update:time /
// update:playing emits. Time still persists across reloads via localStorage.
watch(time, (t) => { localStorage.setItem(`mic_playback_${props.id}`, String(t)); });

function onMediaDurationLoaded(t: number): void {
  if (TOTAL_DURATION.value <= 0 && Number.isFinite(t) && t > 0) TOTAL_DURATION.value = t;
}

async function reloadSpeakers(): Promise<void> {
  try {
    const rows = await speakersApi.list(props.id);
    SPEAKERS_API.value = rows.map((r) => ({
      id: r.id,
      short: r.short ?? null,
      name: r.name ?? null,
      role: r.role ?? null,
      avatar_color: r.avatar_color ?? null,
    }));
  } catch (_) { /* non-fatal */ }
}

// Active segment via O(log n) binary search with VTT-cue-style gap fallback
// (MIC parity — port of mic/frontend/src/stores/playback.js:42-73). Preserves
// the boundary-preferring fix: t > seg.end is exclusive, so when t === next.start
// (the case where clicking slide N seeks to slide N's first-segment.start)
// the mid=prev branch falls through with t > prev.end false and t < prev.start
// false, the loop advances, and we return next.
const activeSegment = computed<Segment | undefined>(() => {
  const segs = SEGMENTS.value;
  if (!segs.length) return undefined;
  const t = time.value;
  let lo = 0;
  let hi = segs.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const seg = segs[mid]!;
    if (t < seg.start) hi = mid - 1;
    else if (t > seg.end) lo = mid + 1;
    else return seg;
  }
  // t fell into a gap between segs[hi].end and segs[lo].start. Pick the nearer
  // neighbor (matches MIC's "previously returned strictly preceding segment
  // produced a whole-segment-behind-captions symptom while audio was in a
  // silence" comment in playback.js:63-66).
  const lower = Math.max(0, lo - 1);
  const upper = Math.min(segs.length - 1, lo);
  if (upper === lower) return segs[upper];
  const dLower = t - segs[lower]!.end;
  const dUpper = segs[upper]!.start - t;
  return dUpper < dLower ? segs[upper] : segs[lower];
});

const activeWordIdx = computed(() => {
  const seg = activeSegment.value;
  if (!seg) return -1;
  const dur = Math.max(0.1, seg.end - seg.start);
  const wordCount = seg.text.split(/\s+/).filter(Boolean).length;
  if (wordCount === 0) return -1;
  const t = Math.max(0, Math.min(dur, time.value - seg.start));
  const idx = Math.floor((t / dur) * wordCount);
  return Math.min(wordCount - 1, Math.max(0, idx));
});

const activeSlide = computed(() => SLIDES.value.find((sl) => sl.id === activeSegment.value?.slide_id));

// MIC-parity alignment count (mic/frontend/src/views/EditorView.vue:3218-3220).
// Counts segments that actually got a slide_id from the aligner — not the
// total segment count. Previously the header showed `N/N aligned` which lied
// when the aligner silently failed and left every segment with NULL slide_id.
const alignedCount = computed(() => SEGMENTS.value.filter((s) => s.slide_id != null).length);
const alignedColor = computed(() => {
  if (SEGMENTS.value.length === 0) return 'var(--fg2)';
  const pct = (alignedCount.value / SEGMENTS.value.length) * 100;
  if (pct >= 100) return 'var(--color-green)';
  if (pct >= 80)  return 'var(--color-amber)';
  return 'var(--color-red)';
});

const tab = ref<TabId>(props.initialTab || 'ai');
const rightTab = ref<RightTabId>('admin');
const slideRailMode = ref<'focus' | 'filter'>(
  localStorage.getItem('mic_slide_click_mode') === 'filter' ? 'filter' : 'focus'
);
watch(slideRailMode, (m) => localStorage.setItem('mic_slide_click_mode', m));

const focusedSlideId = ref<string | null>(null);
const activeSlideCollapsed = ref(false);

// IIL signals — compute from real session_speakers metadata if available;
// otherwise return null so AdminTab hides the section. Hardcoded fixtures
// (148 wpm / 2.1%) are gone. The Instructor card was removed entirely —
// SpeakerEditPanel (mounted below AdminTab) is the single source of truth.
const iilSignals = computed(() => null as { cadence_wpm?: number | null; filler_ratio?: number | null } | null);
// F2 closure — switching tabs clears the slide focus (matches React behavior)
watch(tab, () => { focusedSlideId.value = null; });

const leftW  = ref<number>(parseInt(localStorage.getItem('mic_left_w')  || '320') || 320);
const rightW = ref<number>(parseInt(localStorage.getItem('mic_right_w') || '360') || 360);
watch(leftW,  (w) => localStorage.setItem('mic_left_w',  String(w)));
watch(rightW, (w) => localStorage.setItem('mic_right_w', String(w)));

function onResizeLeft(e: MouseEvent): void {
  e.preventDefault();
  const startX = e.clientX, startW = leftW.value;
  const onMove = (ev: MouseEvent): void => { leftW.value = Math.max(120, startW + (ev.clientX - startX)); };
  const onUp = (): void => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
    document.body.classList.remove('is-col-resizing');
  };
  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
  document.body.classList.add('is-col-resizing');
}
function onResizeRight(e: MouseEvent): void {
  e.preventDefault();
  const startX = e.clientX, startW = rightW.value;
  const onMove = (ev: MouseEvent): void => { rightW.value = Math.max(120, startW - (ev.clientX - startX)); };
  const onUp = (): void => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
    document.body.classList.remove('is-col-resizing');
  };
  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
  document.body.classList.add('is-col-resizing');
}

const gridStyle = computed(() => ({
  gridTemplateColumns: `${leftW.value}px 6px minmax(0, 1fr) 6px ${rightW.value}px`,
}));

const placements = ref<Record<string, string | null>>({});

interface AnchorEntry { id: string; kind: 'chat' | 'poll'; t: number; [k: string]: unknown }

const anchorsBySegment = computed<Map<string, AnchorEntry[]>>(() => {
  const m = new Map<string, AnchorEntry[]>();
  CHAT.value.forEach((c) => {
    const segId = placements.value[c.id];
    if (!segId) return;
    if (!m.has(segId)) m.set(segId, []);
    m.get(segId)!.push({ ...c, kind: 'chat' });
  });
  POLLS.value.forEach((p) => {
    const segId = placements.value[p.id];
    if (!segId) return;
    if (!m.has(segId)) m.set(segId, []);
    m.get(segId)!.push({ ...p, kind: 'poll' });
  });
  m.forEach((arr) => arr.sort((a, b) => a.t - b.t));
  return m;
});

function handleRemoveAnchor(itemId: string): void {
  placements.value = { ...placements.value, [itemId]: null };
  const isChat = CHAT.value.some((c) => c.id === itemId);
  const isPoll = POLLS.value.some((p) => p.id === itemId);
  if (isChat) {
    void placementsApi.chatAnchor(props.id, itemId, null).catch(() => {
      toast.push('Could not save chat removal', { tone: 'error' });
    });
  } else if (isPoll) {
    void placementsApi.pollAnchor(props.id, itemId, null).catch(() => {
      toast.push('Could not save poll removal', { tone: 'error' });
    });
  }
}
function handleDropOnSegment(itemId: string, segId: string): void {
  placements.value = { ...placements.value, [itemId]: segId };
  // Persist to backend. Chat vs poll inferred from which collection owns the id.
  const isChat = CHAT.value.some((c) => c.id === itemId);
  const isPoll = POLLS.value.some((p) => p.id === itemId);
  if (isChat) {
    void placementsApi.chatAnchor(props.id, itemId, segId).catch(() => {
      toast.push('Could not save chat placement', { tone: 'error' });
    });
  } else if (isPoll) {
    void placementsApi.pollAnchor(props.id, itemId, segId).catch(() => {
      toast.push('Could not save poll placement', { tone: 'error' });
    });
  }
}
function handlePlaceAtActive(itemId: string): void {
  if (activeSegment.value) handleDropOnSegment(itemId, activeSegment.value.id);
}

// Phase 6.2 — list reorder for chat + polls. Optimistic local mutation
// followed by a single bulk PATCH; on API failure we revert. The
// backend writes order_index per row in the supplied position, so
// subsequent loads return rows in this order via the
// (order_index IS NULL) ASC, order_index ASC, sent_at_ms ASC tie-break.
function handleChatReorder(ids: readonly string[]): void {
  const before = CHAT.value.slice();
  const byId = new Map(before.map((c) => [c.id, c] as const));
  const next = ids.map((id) => byId.get(id)).filter((c): c is NonNullable<typeof c> => !!c);
  // Defensive: if the incoming ids set doesn't match the current list
  // (race with a concurrent add), bail rather than dropping rows.
  if (next.length !== before.length) {
    toast.push('Chat list changed during reorder — refresh and try again', { tone: 'error' });
    return;
  }
  CHAT.value = next;
  void placementsApi.chatReorder(props.id, [...ids]).catch(() => {
    CHAT.value = before;
    toast.push('Could not save chat reorder', { tone: 'error' });
  });
}

function handlePollsReorder(ids: readonly string[]): void {
  const before = POLLS.value.slice();
  const byId = new Map(before.map((p) => [p.id, p] as const));
  const next = ids.map((id) => byId.get(id)).filter((p): p is NonNullable<typeof p> => !!p);
  if (next.length !== before.length) {
    toast.push('Polls list changed during reorder — refresh and try again', { tone: 'error' });
    return;
  }
  POLLS.value = next;
  void placementsApi.pollsReorder(props.id, [...ids]).catch(() => {
    POLLS.value = before;
    toast.push('Could not save polls reorder', { tone: 'error' });
  });
}

// Phase B2 — inline chat edit. Optimistic local CHAT array patch +
// chat_edit correction POST. Backend segment_id is the placement
// segment (chat must be placed to be editable; the ChatTab only shows
// the Edit button on placed rows). Revert on API failure.
async function handleChatEdit(chatId: string, newText: string): Promise<void> {
  const idx = CHAT.value.findIndex((c) => c.id === chatId);
  if (idx < 0) return;
  const prior = CHAT.value[idx]!;
  const placedSegId = placements.value[chatId];
  if (!placedSegId) {
    toast.push('Edit only available for placed chat', { tone: 'warn' });
    return;
  }
  CHAT.value[idx] = { ...prior, text: newText };
  try {
    await correctionsApi.apply(props.id, {
      segment_id:      placedSegId,
      correction_type: 'chat_edit',
      old_text:        prior.text,
      new_text:        newText,
    });
    toast.push('Chat edit saved', { tone: 'success' });
  } catch (e) {
    // Revert.
    CHAT.value[idx] = prior;
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Save failed';
    toast.push(msg, { tone: 'error' });
  }
}

function onSlideClick(slideId: string): void {
  focusedSlideId.value = slideId;
  if (slideRailMode.value === 'focus') {
    const segs = segmentsBySlide.value.get(slideId);
    if (segs && segs.length) time.value = segs[0]!.start;
  }
}
function onSegmentClick(segId: string): void {
  const s = segmentsById.value.get(segId);
  if (s) time.value = s.start;
}
function onWordClick(segId: string, w: number): void {
  const s = segmentsById.value.get(segId);
  if (!s) return;
  const dur = s.end - s.start;
  const wordCount = s.text.split(/\s+/).filter(Boolean).length;
  if (wordCount === 0) return;
  time.value = s.start + (w / wordCount) * dur;
}
function onScrubClick(e: MouseEvent): void {
  if (TOTAL_DURATION.value === 0) return;
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
  const pct = (e.clientX - rect.left) / rect.width;
  time.value = Math.max(0, Math.min(TOTAL_DURATION.value, pct * TOTAL_DURATION.value));
}

const counts = computed(() => ({
  ai:    SEGMENTS.value.length,
  stt:   SEGMENTS.value.length,
  disc:  DISCREPANCIES.value.filter((d) => d.is_meaningful === true).length,
  audit: CORRECTIONS.value.length,
}));

interface FlagCounts {
  medication: number; name: number; number: number; date: number; terminology: number;
  filler: number; punctuation: number; style: number; other: number;
  uncertain: number; drift: number; low_conf: number;
}

const flagCounts = computed<FlagCounts>(() => {
  const c: FlagCounts = {
    medication: 0, name: 0, number: 0, date: 0, terminology: 0,
    filler: 0, punctuation: 0, style: 0, other: 0,
    uncertain: 0, drift: 0, low_conf: 0,
  };
  SEGMENTS.value.forEach((s) => {
    s.ai_flags.forEach((f) => {
      if (f.kind === 'uncertain')      c.uncertain++;
      if (f.kind === 'drift')          c.drift++;
      if (f.kind === 'low_confidence') c.low_conf++;
    });
  });
  DISCREPANCIES.value.forEach((d) => {
    if (d.category === 'drift')          c.drift++;
    if (d.category === 'punctuation')    c.punctuation++;
    if (d.category === 'filler')         c.filler++;
    if (d.category === 'low_confidence') c.low_conf++;
  });
  return c;
});

const flagFilter = ref<string | null>(null);

// Phase A4 — actually filter the segment list when a flag chip is
// clicked. Two-source matching: a segment matches if either its
// ai_flags include the chip's kind OR a Discrepancy with category
// equal to the chip has segment_id == segment.id.
//
// chipId → predicate on (segment, discrepancyCategoriesForSegment Set).
// Chips with no data source (name / number / date / style) return an
// empty Set — the filter yields zero segments, which the UI renders as
// "No segments match this filter."
const visibleSegments = computed(() => {
  const f = flagFilter.value;
  if (!f) return SEGMENTS.value;

  // Build a per-segment Set of discrepancy categories for fast lookup.
  const catsBySeg = new Map<string, Set<string>>();
  DISCREPANCIES.value.forEach((d) => {
    if (!d.segment_id || !d.category) return;
    let s = catsBySeg.get(d.segment_id);
    if (!s) { s = new Set(); catsBySeg.set(d.segment_id, s); }
    s.add(d.category);
  });

  return SEGMENTS.value.filter((seg) => {
    const cats = catsBySeg.get(seg.id);
    if (f === 'uncertain')   return seg.ai_flags.some((af) => af.kind === 'uncertain');
    if (f === 'drift')       return seg.ai_flags.some((af) => af.kind === 'drift') || (cats?.has('drift') ?? false);
    if (f === 'low_conf')    return seg.ai_flags.some((af) => af.kind === 'low_confidence') || (cats?.has('low_confidence') ?? false);
    // Discrepancy-only categories.
    if (f === 'filler' || f === 'punctuation' || f === 'medication' || f === 'terminology' || f === 'other') {
      return cats?.has(f) ?? false;
    }
    // name / number / date / style — no data source today; empty filter result.
    return false;
  });
});

const sessStageIdx = computed(() => SOP_STAGES.findIndex((x) => x.id === sessionStage.value));
const sessStageName = computed(() => SOP_STAGES.find((x) => x.id === sessionStage.value)?.name || '');

function stepperCls(i: number, isCurrent: boolean): string {
  const cls = ['editor__stepper-item'];
  if (isCurrent) cls.push('is-current');
  if (i < sessStageIdx.value) cls.push('is-done');
  return cls.join(' ');
}

const flaggedCats = computed(() => ([
  { id: 'medication',  label: 'Medication',  color: '#C54644', n: flagCounts.value.medication },
  { id: 'name',        label: 'Name',        color: '#B9975B', n: flagCounts.value.name },
  { id: 'number',      label: 'Number',      color: '#B75D04', n: flagCounts.value.number },
  { id: 'date',        label: 'Date',        color: '#0861CE', n: 0 },
  { id: 'terminology', label: 'Terminology', color: '#7B1FA2', n: flagCounts.value.terminology },
  { id: 'filler',      label: 'Filler',      color: '#4D6995', n: flagCounts.value.filler },
  { id: 'punctuation', label: 'Punctuation', color: '#4D6995', n: flagCounts.value.punctuation },
  { id: 'style',       label: 'Style',       color: '#4D6995', n: 0 },
  { id: 'other',       label: 'Other',       color: '#4D6995', n: 0 },
]));

const flaggedSecondary = computed(() => ([
  { id: 'uncertain', label: 'Uncertain', n: flagCounts.value.uncertain },
  { id: 'drift',     label: 'Drift',     n: flagCounts.value.drift },
  { id: 'low_conf',  label: 'Low conf',  n: flagCounts.value.low_conf },
]));

// Phase 1 (audit remediation): Undo / Redo / Result handlers + buttons
// removed. Prior versions toasted "Undone"/"Redone" but mutated nothing —
// a data-integrity lie. Phase 4 (corrections API) re-introduces them with
// real undo-stack persistence + AI-result history.
function onPreview(): void { router.push(`/v/${props.id}`); }

// Phase B1 — DiscrepanciesPane handlers.
// onDiscRequestEdit: pivot to AI tab + emit segmentClick so TranscriptPane
// scrolls to and (in future iterations) opens inline edit on this segment.
function onDiscRequestEdit(segId: string): void {
  tab.value = 'ai';
  // Defer the scroll until the AI tab is mounted (next tick).
  void Promise.resolve().then(() => onSegmentClick(segId));
}
// onDiscrepancyResolved: optimistic removal of any discrepancy rows tied
// to this segment from the local DISCREPANCIES array. Backend has already
// flipped resolved=true via the mark_ok correction; refetching the full
// list would be one wasted round-trip.
function onDiscrepancyResolved(segId: string): void {
  DISCREPANCIES.value = DISCREPANCIES.value.filter((d) => d.segment_id !== segId);
}
function openFind(): void {
  void modal.open(
    FindReplaceModal,
    { sessionId: props.id, onApplied: () => { void load(); } },
    { mode: 'ribbon' },
  );
}

// ── Inline-save handlers (Phase C.3) ─────────────────────────────────
async function onEditSegment(segId: string, before: string, after: string): Promise<void> {
  try {
    await correctionsApi.apply(props.id, {
      segment_id: segId, correction_type: 'text_edit',
      old_text: before, new_text: after,
    });
    const idx = SEGMENTS.value.findIndex((s) => s.id === segId);
    if (idx >= 0) {
      SEGMENTS.value[idx] = { ...SEGMENTS.value[idx]!, text: after, has_user_override: true };
    }
    toast.push('Edit saved', { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Save failed';
    toast.push(msg, { tone: 'error' });
  }
}

// Phase 2 — autosave on textarea blur / segment-switch. Backend
// _is_noop_correction (Phase 1.5) short-circuits when nothing changed,
// so calling on every blur is safe for the redo tail. Optimistic local
// update mirrors the manual-save path so the UI keeps the edited text
// even if the next refresh hasn't run yet.
function onAutosaveSegment(segId: string, before: string, after: string): void {
  if (before === after) return;
  const idx = SEGMENTS.value.findIndex((s) => s.id === segId);
  if (idx >= 0) {
    SEGMENTS.value[idx] = { ...SEGMENTS.value[idx]!, text: after, has_user_override: true };
  }
  autosave.schedule(segId, before, after);
}
function onFlushAutosave(segId?: string): void {
  autosave.flush(segId);
}

async function onReassignSegment(segId: string, beforeSlide: string | null, afterSlide: string): Promise<void> {
  try {
    await correctionsApi.apply(props.id, {
      segment_id: segId, correction_type: 'slide_reassignment',
      old_slide_id: beforeSlide, new_slide_id: afterSlide,
    });
    const idx = SEGMENTS.value.findIndex((s) => s.id === segId);
    if (idx >= 0) {
      SEGMENTS.value[idx] = { ...SEGMENTS.value[idx]!, slide_id: afterSlide };
    }
    toast.push('Reassigned to new slide', { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Reassign failed';
    toast.push(msg, { tone: 'error' });
  }
}

async function onReassignSpeakerLive(segId: string, _beforeSpeakerId: string | null, afterSpeakerId: string): Promise<void> {
  try {
    await speakersApi.reassignSegment(props.id, segId, afterSpeakerId);
    const sp = SPEAKERS_API.value.find((s) => s.id === afterSpeakerId);
    const idx = SEGMENTS.value.findIndex((s) => s.id === segId);
    if (idx >= 0 && sp) {
      // splice() guarantees array-mutation reactivity even when the runtime
      // is wrapping SEGMENTS in something other than a plain Proxy. Direct
      // index assignment SHOULD also work but reports came in that the chip
      // didn't update — splice is the belt-and-suspenders fix.
      const updated: Segment = {
        ...SEGMENTS.value[idx]!,
        speaker_id:    sp.id,
        speaker_name:  sp.name,
        speaker_short: sp.short,
        speaker_color: sp.avatar_color ?? null,
        speaker_role:  sp.role,
      };
      SEGMENTS.value.splice(idx, 1, updated);
    }
    toast.push(`Speaker → ${sp?.name || 'updated'}`, { tone: 'success' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Speaker change failed';
    toast.push(msg, { tone: 'error' });
  }
}

// ── Undo / Redo (Phase C.4) ──────────────────────────────────────────
async function onUndo(): Promise<void> {
  try {
    await correctionsApi.undo(props.id);
    await load();
    toast.push('Undone', { tone: 'info' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Undo failed';
    toast.push(msg, { tone: 'error' });
  }
}
async function onRedo(): Promise<void> {
  try {
    await correctionsApi.redo(props.id);
    await load();
    toast.push('Redone', { tone: 'info' });
  } catch (e) {
    const msg = e instanceof ApiError ? `${e.status} — ${e.message}` : 'Redo failed';
    toast.push(msg, { tone: 'error' });
  }
}

const sessionForChildren = computed(() => ({
  id: session.value?.id || props.id,
  presenter: session.value?.presenter || '',
  recorded: '',
}));
const auditSessionRef = computed(() => ({ id: session.value?.id || props.id }));

onMounted(() => { document.body.classList.add('has-editor'); });
onUnmounted(() => { document.body.classList.remove('has-editor'); });

// ── Keyboard shortcuts (Phase A2) ────────────────────────────────────
// Cmd/Ctrl+Z      → onUndo()
// Shift+Cmd/Ctrl+Z → onRedo()
// Cmd/Ctrl+F      → openFind()
//
// Guarded against input/textarea focus so the browser's native undo
// inside a focused segment-edit textarea still works. The toolbar's
// own undo/redo (inline.history / inline.redo) manages the segment
// draft separately and shouldn't be hijacked by the global handler.
function onEditorKeydown(e: KeyboardEvent): void {
  // Modifier required for all three shortcuts.
  const mod = e.metaKey || e.ctrlKey;
  if (!mod) return;

  // Let textareas / inputs / contenteditable own their native shortcuts.
  const target = e.target as HTMLElement | null;
  if (target) {
    const tag = target.tagName;
    if (tag === 'TEXTAREA' || tag === 'INPUT' || target.isContentEditable) return;
  }

  const k = e.key.toLowerCase();
  if (k === 'z' && !e.shiftKey) {
    e.preventDefault();
    void onUndo();
  } else if ((k === 'z' && e.shiftKey) || k === 'y') {
    // Cmd+Shift+Z (mac convention) OR Ctrl+Y (windows convention) → redo
    e.preventDefault();
    void onRedo();
  } else if (k === 'f') {
    e.preventDefault();
    openFind();
  }
}

onMounted(() => { window.addEventListener('keydown', onEditorKeydown); });
onUnmounted(() => { window.removeEventListener('keydown', onEditorKeydown); });
</script>

<template>
  <div class="editor" :data-screen-label="`Editor / ${props.id}`" :data-readonly="isReadOnly">
    <!-- Phase 1 (2026-06-05): concurrent-edit lock banners. Fail-closed —
         when lockError is set OR another user holds the lock, the editor
         enters read-only mode. The autosave gate (Phase 2) consumes
         isReadOnly to skip writes. -->
    <div
      v-if="lockError"
      class="editor__lock-banner editor__lock-banner--error"
      role="alert"
      data-test-id="editor-lock-banner-error"
    >
      <Icon name="alert" :size="14" />
      <span>
        <strong>Lock service unavailable</strong> — edits are disabled until the lock service is reachable.
        Click Retry to try again.
      </span>
      <button type="button" class="btn btn--ghost btn--sm" @click="() => { void forceTake(); }">Retry</button>
    </div>
    <div
      v-else-if="isReadOnly && holder"
      class="editor__lock-banner editor__lock-banner--warn"
      role="status"
      data-test-id="editor-lock-banner-readonly"
    >
      <Icon name="lock" :size="14" />
      <span>
        <strong>In use by {{ holder.user_email }}</strong> — you have read-only access. The lock auto-expires at
        {{ new Date(holder.expires_at).toLocaleTimeString() }}.
      </span>
      <button
        v-if="isAdmin"
        type="button"
        class="btn btn--secondary btn--sm"
        data-test-id="editor-lock-force-take"
        @click="() => { void forceTake(); }"
      >Force-take (admin)</button>
    </div>

    <!-- Phase 1 (2026-06-05): editor skeleton renders while the very first
         data load is in flight. The existing per-stage loadbar still
         renders for granular progress once SEGMENTS start arriving. -->
    <EditorSkeleton v-if="loading && SEGMENTS.length === 0" />

    <!-- Phase A7 — per-stage load progress strip. Shows only during the
         initial load; non-blocking, error-tolerant per stage. -->
    <div
      v-if="loading && SEGMENTS.length > 0"
      class="editor__loadbar"
      :class="loadHasError ? 'editor__loadbar--has-error' : ''"
      data-test-id="editor-loadbar"
    >
      <div class="editor__loadbar-fill" :style="{ width: `${loadProgressPct}%` }" />
      <div class="editor__loadbar-stages">
        <span
          v-for="(state, key) in loadStages"
          :key="key"
          :class="['editor__loadbar-stage', `is-${state}`]"
          :title="`${LOAD_STAGE_LABELS[key]}: ${state}`"
        >{{ LOAD_STAGE_LABELS[key] }}</span>
      </div>
    </div>
    <div class="editor__topbar">
      <div class="page-eyebrow" :style="{ marginBottom: '6px' }">
        <RouterLink to="/sessions">Sessions</RouterLink><span class="sep">/</span>
        <RouterLink :to="`/s/${props.id}`">
          <code :style="{ fontFamily: 'var(--font-mono)', color: 'var(--fg-link)' }">{{ sessionCode }}</code>
        </RouterLink><span class="sep">/</span>
        <span>Editor</span>
      </div>

      <div class="editor__stepper" role="navigation" aria-label="SOP stages">
        <template v-for="(st, i) in SOP_STAGES" :key="st.id">
          <RouterLink :to="`/e/${props.id}/sop`" :class="stepperCls(i, st.id === sessionStage)">
            <span class="dot" /> {{ st.name }}
          </RouterLink>
          <span v-if="i < SOP_STAGES.length - 1" class="editor__stepper-sep">▸</span>
        </template>
        <span
          v-if="pipelineCfg"
          :style="{ marginLeft: 'auto', fontSize: '10px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: pipelineCfg.ai_pipeline === 'direct' ? 'var(--color-navy)' : 'var(--color-amber)', padding: '2px 8px', border: `1px solid ${pipelineCfg.ai_pipeline === 'direct' ? 'var(--color-navy)' : 'var(--color-amber)'}`, borderRadius: '999px' }"
          :title="`Pipeline: ${pipelineCfg.ai_pipeline} | mode: ${pipelineCfg.ai_mode} | model: ${pipelineCfg.ai_model}`"
        >
          AI: {{ pipelineCfg.ai_pipeline }}
        </span>
        <span :style="{ marginLeft: pipelineCfg ? '8px' : 'auto', fontSize: '10px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: session?.status === 'ready' || session?.status === 'complete' ? 'var(--color-green)' : 'var(--fg2)' }">
          <Icon name="check" :size="11" /> {{ session?.status === 'ready' || session?.status === 'complete' ? 'AI ready' : (session?.status || 'pending') }}
        </span>
      </div>

      <div class="editor__title-row">
        <h1 class="editor__title editor__title--mono">{{ sessionCode }}</h1>
        <div class="page-actions">
          <button class="btn btn--ghost btn--sm" data-test-id="editor-undo" title="Undo (⌘Z)" @click="onUndo">
            <Icon name="history" /> Undo
          </button>
          <button class="btn btn--ghost btn--sm" data-test-id="editor-redo" title="Redo (⇧⌘Z)" :style="{ transform: 'scaleX(-1)' }" @click="onRedo">
            <Icon name="history" />
          </button>
          <button class="btn btn--secondary btn--sm" data-test-id="editor-preview" title="Preview rendered output" @click="onPreview">
            <Icon name="external" /> Preview
          </button>
        </div>
      </div>

      <div class="editor__subrow">
        <span class="editor__align">
          <span :style="{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: alignedColor }">{{ alignedCount }}/{{ SEGMENTS.length }}</span> aligned
        </span>
        <button class="btn btn--secondary btn--sm" data-test-id="editor-find-replace" @click="openFind">
          <Icon name="search" /> Find &amp; Replace
        </button>
        <span :style="{ marginLeft: 'auto', display: 'inline-flex', gap: '8px', alignItems: 'center' }">
          <span class="stage-badge stage-badge--prep" :style="{ textTransform: 'uppercase' }">{{ sessStageName }}</span>
          <RouterLink :to="`/e/${props.id}/sop`" class="btn btn--ghost btn--sm"><Icon name="branch" /> Workflow</RouterLink>
          <RouterLink :to="`/e/${props.id}/audit`" class="btn btn--ghost btn--sm"><Icon name="history" /> Audit</RouterLink>
          <DownloadMenu :code="sessionCode" :session-id="props.id" />
        </span>
      </div>

      <div class="editor__flagged">
        <span class="editor__flagged-label">Flagged:</span>
        <button
          v-for="f in flaggedCats"
          :key="f.id"
          :class="['editor__flag-chip', f.n === 0 ? 'is-empty' : '', flagFilter === f.id ? 'is-active' : '']"
          @click="flagFilter = flagFilter === f.id ? null : f.id"
        >
          <span class="dot" :style="{ background: f.color }" /> {{ f.label }} ({{ f.n }})
        </button>
        <span class="editor__flagged-divider" />
        <button
          v-for="f in flaggedSecondary"
          :key="f.id"
          :class="['editor__flag-chip', f.n === 0 ? 'is-empty' : '', flagFilter === f.id ? 'is-active' : '']"
          @click="flagFilter = flagFilter === f.id ? null : f.id"
        >
          <span class="dot" /> {{ f.label }} ({{ f.n }})
        </button>
      </div>
    </div>

    <div class="editor__tabs" role="tablist">
      <button :class="['editor__tab', tab === 'ai' ? 'is-active' : '']" role="tab" @click="tab = 'ai'">
        <Icon name="doc" /> AI Transcript <span class="count">{{ counts.ai }}</span>
      </button>
      <button :class="['editor__tab', tab === 'stt' ? 'is-active' : '']" role="tab" @click="tab = 'stt'">
        <Icon name="speaker" /> STT Reference <span class="count">{{ counts.stt }}</span>
      </button>
      <button :class="['editor__tab', tab === 'disc' ? 'is-active' : '']" role="tab" @click="tab = 'disc'">
        <Icon name="git" /> Discrepancies
        <span
          v-if="counts.disc > 0"
          class="count count--amber"
          :aria-label="`${counts.disc} unresolved discrepanc${counts.disc === 1 ? 'y' : 'ies'}`"
          data-test-id="disc-tab-count"
        >{{ counts.disc }}</span>
      </button>
      <button :class="['editor__tab', tab === 'audit' ? 'is-active' : '']" role="tab" @click="tab = 'audit'">
        <Icon name="history" /> Audit
        <span v-if="counts.audit > 0" class="tab-indicator" aria-label="Has audit entries"></span>
      </button>
      <div class="editor__tab-spacer" />
      <div class="editor__tab-meta"><FlagLegend /></div>
    </div>

    <div class="editor__grid" :style="gridStyle">
      <aside class="editor__leftcol">
        <VideoStrip
          :session="sessionForChildren"
          :active-slide="activeSlide"
          :slides="SLIDES"
          :time="time"
          :total="TOTAL_DURATION"
          :playing="playing"
          :rate="rate"
          :cc="cc"
          :segments-by-slide="segmentsBySlide"
          :media-url="mediaUrl"
          :media-kind="mediaKind"
          @toggle-play="playing = !playing"
          @update:rate="(r) => (rate = r)"
          @update:cc="(v) => (cc = v)"
          @update:time="(t) => (time = t)"
          @update:playing="(v) => (playing = v)"
          @update:total="onMediaDurationLoaded"
          @scrub-click="onScrubClick"
          @seek-to="(s: number) => { time = TOTAL_DURATION > 0 ? Math.max(0, Math.min(TOTAL_DURATION, s)) : Math.max(0, s); }"
        />
        <SlideRail
          :slides="SLIDES"
          :active-slide-id="activeSlide?.id"
          :focused-slide-id="focusedSlideId"
          :mode="slideRailMode"
          :segments-by-slide="segmentsBySlide"
          @mode-change="(m) => { slideRailMode = m; focusedSlideId = null; }"
          @clear-focus="focusedSlideId = null"
          @slide-click="onSlideClick"
        />
      </aside>
      <div class="editor__resizer" title="Drag to resize" @mousedown="onResizeLeft" />

      <TranscriptPane
        v-if="tab === 'ai'"
        :segments="visibleSegments"
        :active-segment-id="activeSegment?.id"
        :active-word-idx="activeWordIdx"
        :focused-slide-id="focusedSlideId"
        :slide-rail-mode="slideRailMode"
        :anchors-by-segment="anchorsBySegment as any"
        :live-speakers="SPEAKERS_API"
        :live-slides="SLIDES"
        :live-alignment="ALIGNMENT_BY_SEGMENT"
        :time="time"
        @segment-click="onSegmentClick"
        @word-click="onWordClick"
        @clear-focus="focusedSlideId = null"
        @drop-on-segment="handleDropOnSegment"
        @remove-anchor="handleRemoveAnchor"
        @edit-segment="onEditSegment"
        @autosave-segment="onAutosaveSegment"
        @flush-autosave="onFlushAutosave"
        @reassign-segment="onReassignSegment"
        @reassign-speaker-live="onReassignSpeakerLive"
      />
      <STTPane
        v-else-if="tab === 'stt'"
        :segments="SEGMENTS"
        :active-segment-id="activeSegment?.id"
        :active-word-idx="activeWordIdx"
        :focused-slide-id="focusedSlideId"
        :slide-rail-mode="slideRailMode"
        :stt-ready="sttReady"
        :stt-failed="sttFailed"
        :live-words="WORDS_BY_SEGMENT"
        :live-slides="SLIDES"
        @segment-click="onSegmentClick"
        @word-click="onWordClick"
        @clear-focus="focusedSlideId = null"
      />
      <DiscrepanciesPane
        v-else-if="tab === 'disc'"
        :active-segment-id="activeSegment?.id"
        :focused-slide-id="focusedSlideId"
        :slide-rail-mode="slideRailMode"
        :live-segments="SEGMENTS"
        :live-slides="SLIDES"
        :live-discrepancies="DISCREPANCIES"
        :live-words="WORDS_BY_SEGMENT"
        :session-id="props.id"
        @segment-click="onSegmentClick"
        @clear-focus="focusedSlideId = null"
        @request-edit="onDiscRequestEdit"
        @discrepancy-resolved="onDiscrepancyResolved"
      />
      <AuditTabInline
        v-else
        :session="auditSessionRef"
        :active-segment-id="activeSegment?.id"
        :live-corrections="CORRECTIONS"
        :live-segments="SEGMENTS"
        @segment-click="onSegmentClick"
      />

      <div class="editor__resizer" title="Drag to resize" @mousedown="onResizeRight" />

      <aside
        v-if="tab === 'stt'"
        class="rightrail"
        aria-label="STT Reference side panel"
        data-screen-label="STT Right Rail"
      >
        <!-- Slide context stays visible on the STT tab so the operator can
             read STT tokens against the slide the speaker was on at that
             moment. Deviates from MIC editor.jsx:1413 which only showed
             STTSidePanel here — explicit user-requested expansion. -->
        <ActiveSlideCard
          :slide="activeSlide"
          :segment-count="segmentsBySlide.get(activeSlide?.id || '')?.length || 0"
          :collapsed="activeSlideCollapsed"
          :time="time"
          :total-duration="TOTAL_DURATION"
          :live-slides="SLIDES"
          :live-segments="SEGMENTS"
          @toggle="activeSlideCollapsed = !activeSlideCollapsed"
        />
        <STTSidePanel
          :time="time"
          :total-duration="TOTAL_DURATION"
          :segments="SEGMENTS"
          :live-discrepancies="DISCREPANCIES"
        />
      </aside>
      <aside v-else class="rightrail" aria-label="Side panel" data-screen-label="Right Rail">
        <ActiveSlideCard
          :slide="activeSlide"
          :segment-count="segmentsBySlide.get(activeSlide?.id || '')?.length || 0"
          :collapsed="activeSlideCollapsed"
          :time="time"
          :total-duration="TOTAL_DURATION"
          :live-slides="SLIDES"
          :live-segments="SEGMENTS"
          @toggle="activeSlideCollapsed = !activeSlideCollapsed"
        />
        <div class="rightrail__tabs" role="tablist">
          <button :class="['rightrail__tab', rightTab === 'admin' ? 'is-active' : '']" role="tab" @click="rightTab = 'admin'">
            <Icon name="user" /> Admin
          </button>
          <button :class="['rightrail__tab', rightTab === 'chat' ? 'is-active' : '']" role="tab" @click="rightTab = 'chat'">
            <Icon name="message" /> Chat <span class="count">{{ CHAT.length }}</span>
          </button>
          <button :class="['rightrail__tab', rightTab === 'polls' ? 'is-active' : '']" role="tab" @click="rightTab = 'polls'">
            <Icon name="list" /> Polls <span class="count">{{ POLLS.length }}</span>
          </button>
        </div>
        <div class="rightrail__panel">
          <template v-if="rightTab === 'admin'">
            <AdminTab
              :slide="activeSlide"
              :segments="SEGMENTS"
              :time="time"
              :total-duration="TOTAL_DURATION"
              :slides="SLIDES"
              :iil="iilSignals"
              :session-id="props.id"
            />
            <SpeakerEditPanel
              :session-id="props.id"
              :live-speakers="SPEAKERS_API"
              @changed="reloadSpeakers"
            />
          </template>
          <ChatTab
            v-else-if="rightTab === 'chat'"
            :chat="CHAT"
            :slides="SLIDES"
            :segments-by-id="segmentsById"
            :placements="placements"
            @unplace="handleRemoveAnchor"
            @place-at-active="handlePlaceAtActive"
            @reorder="handleChatReorder"
            @edit-chat="handleChatEdit"
          />
          <PollsTab
            v-else
            :polls="POLLS"
            :segments-by-id="segmentsById"
            :slides="SLIDES"
            :placements="placements"
            @unplace="handleRemoveAnchor"
            @place-at-active="handlePlaceAtActive"
            @reorder="handlePollsReorder"
          />
        </div>
      </aside>
    </div>

    <div class="editor__statusbar">
      <span class="dot" /> {{ loading ? 'loading' : 'ready' }} · {{ SEGMENTS.length }} segments · {{ SLIDES.length }} slides
      <span class="sep" />
      <span>autosave <code>—</code></span>
      <span class="sep" />
      <span>session: <code>{{ session?.status || '—' }}</code></span>
      <span class="end">
        <span>shortcut: <code>?</code></span>
        <span class="sep" />
        <span :title="`Bundle: ${bundleSha}`">build <code>{{ bundleShort }}</code></span>
      </span>
    </div>
  </div>
</template>
