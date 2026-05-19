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
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
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
import ChatTab from '@/components/editor/ChatTab.vue';
import PollsTab from '@/components/editor/PollsTab.vue';
import DownloadMenu from '@/components/editor/DownloadMenu.vue';
import { sessions as sessionsApi, segments as segmentsApi, audit as auditApi, corrections as correctionsApi, speakers as speakersApi, words as wordsApi, discrepancies as discrepanciesApi, type SessionSummary, type WordRow, type DiscrepancyRow } from '@/services/api';
import { toast } from '@/composables/useToast';
import { ApiError } from '@/services/http';
import { http } from '@/services/http';
import type { Segment, Slide } from '@/fixtures/transcript';
import type { ChatMessage, Poll } from '@/fixtures/chat_polls';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { modal } from '@/composables/useModal';
import FindReplaceModal from '@/components/overlays/FindReplaceModal.vue';
import { useSyncController } from '@/composables/useSyncController';

type TabId = 'ai' | 'stt' | 'disc' | 'audit';
type RightTabId = 'admin' | 'chat' | 'polls';

const props = defineProps<{ id: string; initialTab?: TabId }>();
const router = useRouter();

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
const loading = ref(true);

const TOTAL_DURATION = computed(() => session.value?.duration_sec ?? 0);
const sessionCode = computed(() => session.value?.code || props.id);
const sessionStage = computed(() => 'prep'); // until /sop wiring lands per-editor

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [s, sg, sl, sp, ch, po, di, co, wd] = await Promise.all([
      sessionsApi.get(props.id).catch(() => null),
      segmentsApi.list(props.id).catch(() => []),
      http<Slide[]>(`/v1/sessions/${encodeURIComponent(props.id)}/slides`).catch(() => []),
      http<ApiSpeaker[]>(`/v1/sessions/${encodeURIComponent(props.id)}/speakers`).catch(() => []),
      http<ChatMessage[]>(`/v1/sessions/${encodeURIComponent(props.id)}/chat`).catch(() => []),
      http<Poll[]>(`/v1/sessions/${encodeURIComponent(props.id)}/polls`).catch(() => []),
      discrepanciesApi.list(props.id).catch(() => ({ session_id: props.id, count: 0, classified_count: 0, classification_status: 'pending' as const, discrepancies: [] as DiscrepancyRow[] })),
      auditApi.corrections(props.id).catch(() => []),
      wordsApi.listBySession(props.id).catch(() => [] as WordRow[]),
    ]);
    session.value = s;
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
  } finally {
    loading.value = false;
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

onMounted(() => { void load(); wsConnect(); });
onUnmounted(() => { wsDisconnect(); });

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

let rafId = 0;
let lastTick = 0;

watch(time, (t) => { localStorage.setItem(`mic_playback_${props.id}`, String(t)); });

watch(playing, (p) => {
  cancelAnimationFrame(rafId);
  lastTick = 0;
  if (!p) return;
  const step = (now: number) => {
    if (!lastTick) lastTick = now;
    const dt = (now - lastTick) / 1000;
    lastTick = now;
    const next = time.value + dt * rate.value;
    if (next >= TOTAL_DURATION.value) { time.value = TOTAL_DURATION.value; playing.value = false; return; }
    time.value = next;
    rafId = requestAnimationFrame(step);
  };
  rafId = requestAnimationFrame(step);
});

onUnmounted(() => { cancelAnimationFrame(rafId); });

const activeSegment = computed<Segment | undefined>(() => {
  const segs = SEGMENTS.value;
  for (let i = 0; i < segs.length; i++) {
    if (time.value >= segs[i]!.start && time.value < segs[i]!.end + 0.25) return segs[i];
  }
  return segs[segs.length - 1];
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

const tab = ref<TabId>(props.initialTab || 'ai');
const rightTab = ref<RightTabId>('chat');
const slideRailMode = ref<'focus' | 'filter'>(
  localStorage.getItem('mic_slide_click_mode') === 'filter' ? 'filter' : 'focus'
);
watch(slideRailMode, (m) => localStorage.setItem('mic_slide_click_mode', m));

const focusedSlideId = ref<string | null>(null);
const activeSlideCollapsed = ref(false);
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
}
function handleDropOnSegment(itemId: string, segId: string): void {
  placements.value = { ...placements.value, [itemId]: segId };
}
function handlePlaceAtActive(itemId: string): void {
  if (activeSegment.value) handleDropOnSegment(itemId, activeSegment.value.id);
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
</script>

<template>
  <div class="editor" :data-screen-label="`Editor / ${props.id}`">
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
        <span :style="{ marginLeft: 'auto', fontSize: '10px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: session?.status === 'ready' || session?.status === 'complete' ? 'var(--color-green)' : 'var(--fg2)' }">
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
          <span :style="{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--color-green)' }">{{ SEGMENTS.length }}/{{ SEGMENTS.length }}</span> aligned
        </span>
        <button class="btn btn--secondary btn--sm" data-test-id="editor-find-replace" @click="openFind">
          <Icon name="search" /> Find &amp; Replace
        </button>
        <span :style="{ marginLeft: 'auto', display: 'inline-flex', gap: '8px', alignItems: 'center' }">
          <span class="stage-badge stage-badge--prep" :style="{ textTransform: 'uppercase' }">{{ sessStageName }}</span>
          <RouterLink :to="`/e/${props.id}/sop`" class="btn btn--ghost btn--sm"><Icon name="branch" /> Workflow</RouterLink>
          <RouterLink :to="`/e/${props.id}/audit`" class="btn btn--ghost btn--sm"><Icon name="history" /> Audit</RouterLink>
          <DownloadMenu :code="sessionCode" />
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
        <span v-if="counts.disc > 0" class="tab-indicator" aria-label="Has meaningful diffs"></span>
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
          @toggle-play="playing = !playing"
          @update:rate="(r) => (rate = r)"
          @update:cc="(v) => (cc = v)"
          @scrub-click="onScrubClick"
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
        :segments="SEGMENTS"
        :active-segment-id="activeSegment?.id"
        :active-word-idx="activeWordIdx"
        :focused-slide-id="focusedSlideId"
        :slide-rail-mode="slideRailMode"
        :anchors-by-segment="anchorsBySegment as any"
        :live-speakers="SPEAKERS_API"
        :live-slides="SLIDES"
        @segment-click="onSegmentClick"
        @word-click="onWordClick"
        @clear-focus="focusedSlideId = null"
        @drop-on-segment="handleDropOnSegment"
        @remove-anchor="handleRemoveAnchor"
        @edit-segment="onEditSegment"
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
        @segment-click="onSegmentClick"
        @clear-focus="focusedSlideId = null"
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

      <STTSidePanel
        v-if="tab === 'stt'"
        :time="time"
        :total-duration="TOTAL_DURATION"
        :segments="SEGMENTS"
        :live-discrepancies="DISCREPANCIES"
      />
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
          <AdminTab
            v-if="rightTab === 'admin'"
            :slide="activeSlide"
            :segments="SEGMENTS"
            :time="time"
            :total-duration="TOTAL_DURATION"
            :slides="SLIDES"
          />
          <ChatTab
            v-else-if="rightTab === 'chat'"
            :chat="CHAT"
            :slides="SLIDES"
            :segments-by-id="segmentsById"
            :placements="placements"
            @unplace="handleRemoveAnchor"
            @place-at-active="handlePlaceAtActive"
          />
          <PollsTab
            v-else
            :polls="POLLS"
            :segments-by-id="segmentsById"
            :slides="SLIDES"
            :placements="placements"
            @unplace="handleRemoveAnchor"
            @place-at-active="handlePlaceAtActive"
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
        <span>build <code>v4.0.0-ssot-r2</code></span>
      </span>
    </div>
  </div>
</template>
