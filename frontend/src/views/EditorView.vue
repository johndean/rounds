<script setup lang="ts">
/**
 * EditorView — verbatim port of editor.jsx::EditorRoute (972-1552).
 *
 * 3-column resizable layout, 4 tabs (AI · STT · Discrepancies · Audit),
 * mini SOP stepper, flagged filter row, slide rail (focus/filter), karaoke
 * playhead from a rAF loop, persisted column widths and slide-rail mode,
 * inline anchor placement (chat + polls drop on segments), status bar.
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
import { SESSIONS } from '@/fixtures/sessions';
import { SLIDES, SEGMENTS, TOTAL_DURATION, type Segment } from '@/fixtures/transcript';
import { CHAT, POLLS } from '@/fixtures/chat_polls';
import { DISCREPANCIES, CORRECTIONS } from '@/fixtures/audit';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { toast } from '@/composables/useToast';
import { modal } from '@/composables/useModal';
import FindReplaceModal from '@/components/overlays/FindReplaceModal.vue';

type TabId = 'ai' | 'stt' | 'disc' | 'audit';
type RightTabId = 'admin' | 'chat' | 'polls';

const props = defineProps<{ id: string; initialTab?: TabId }>();

const router = useRouter();
const session = computed(() => SESSIONS.find((s) => s.id === props.id) || SESSIONS[0]!);

const segmentsById = computed<Map<string, Segment>>(() => {
  const m = new Map<string, Segment>();
  SEGMENTS.forEach((s) => m.set(s.id, s));
  return m;
});
const segmentsBySlide = computed<Map<string, Segment[]>>(() => {
  const m = new Map<string, Segment[]>();
  SLIDES.forEach((sl) => m.set(sl.id, []));
  SEGMENTS.forEach((s) => { if (s.slide_id) m.get(s.slide_id)?.push(s); });
  return m;
});

const time = ref<number>((() => {
  const v = parseFloat(localStorage.getItem(`mic_playback_${props.id}`) ?? '');
  return isNaN(v) ? 198 : v;
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
    if (next >= TOTAL_DURATION) { time.value = TOTAL_DURATION; playing.value = false; return; }
    time.value = next;
    rafId = requestAnimationFrame(step);
  };
  rafId = requestAnimationFrame(step);
});

onUnmounted(() => { cancelAnimationFrame(rafId); });

const activeSegment = computed<Segment | undefined>(() => {
  for (let i = 0; i < SEGMENTS.length; i++) {
    if (time.value >= SEGMENTS[i]!.start && time.value < SEGMENTS[i]!.end + 0.25) return SEGMENTS[i];
  }
  return SEGMENTS[SEGMENTS.length - 1];
});

const activeWordIdx = computed(() => {
  const seg = activeSegment.value;
  if (!seg) return -1;
  const dur = Math.max(0.1, seg.end - seg.start);
  const wordCount = seg.text.split(/\s+/).filter(Boolean).length;
  const t = Math.max(0, Math.min(dur, time.value - seg.start));
  const idx = Math.floor((t / dur) * wordCount);
  return Math.min(wordCount - 1, Math.max(0, idx));
});

const activeSlide = computed(() => SLIDES.find((sl) => sl.id === activeSegment.value?.slide_id));

const tab = ref<TabId>(props.initialTab || 'ai');
const rightTab = ref<RightTabId>('chat');
const slideRailMode = ref<'focus' | 'filter'>(
  localStorage.getItem('mic_slide_click_mode') === 'filter' ? 'filter' : 'focus'
);
watch(slideRailMode, (m) => localStorage.setItem('mic_slide_click_mode', m));

const focusedSlideId = ref<string | null>(null);
const activeSlideCollapsed = ref(false);

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

const initialPlacements: Record<string, string | null> = (() => {
  const m: Record<string, string | null> = {};
  CHAT.forEach((c) => { m[c.id] = c.placed ? c.anchor : null; });
  POLLS.forEach((p) => { m[p.id] = p.placed ? p.anchor : null; });
  return m;
})();
const placements = ref<Record<string, string | null>>({ ...initialPlacements });

interface AnchorEntry {
  id: string;
  kind: 'chat' | 'poll';
  t: number;
  [k: string]: unknown;
}

const anchorsBySegment = computed<Map<string, AnchorEntry[]>>(() => {
  const m = new Map<string, AnchorEntry[]>();
  CHAT.forEach((c) => {
    const segId = placements.value[c.id];
    if (!segId) return;
    if (!m.has(segId)) m.set(segId, []);
    m.get(segId)!.push({ ...c, kind: 'chat' });
  });
  POLLS.forEach((p) => {
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
  time.value = s.start + (w / wordCount) * dur;
}
function onScrubClick(e: MouseEvent): void {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
  const pct = (e.clientX - rect.left) / rect.width;
  time.value = Math.max(0, Math.min(TOTAL_DURATION, pct * TOTAL_DURATION));
}

const counts = computed(() => ({
  ai:    SEGMENTS.length,
  stt:   SEGMENTS.length,
  disc:  DISCREPANCIES.filter((d) => d.status === 'open' && d.meaningful).length,
  audit: CORRECTIONS.length,
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
  SEGMENTS.forEach((s) => {
    s.ai_flags.forEach((f) => {
      if (f.kind === 'uncertain')      c.uncertain++;
      if (f.kind === 'drift')          c.drift++;
      if (f.kind === 'low_confidence') c.low_conf++;
    });
  });
  DISCREPANCIES.forEach((d) => {
    if (d.kind === 'drift')          c.drift++;
    if (d.kind === 'punctuation')    c.punctuation++;
    if (d.kind === 'filler')         c.filler++;
    if (d.kind === 'low_confidence') c.low_conf++;
  });
  c.medication = 4;
  c.terminology = 12;
  c.name = 2;
  c.number = 2;
  return c;
});

const flagFilter = ref<string | null>(null);

const sessStageIdx = computed(() => SOP_STAGES.findIndex((x) => x.id === session.value.stage));
const sessStageName = computed(() => SOP_STAGES.find((x) => x.id === session.value.stage)?.name || '');

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

function onUndo(): void  { toast.push('Undone', { tone: 'info' }); }
function onRedo(): void  { toast.push('Redone', { tone: 'info' }); }
function onResult(): void { toast.push('Last AI result — opening side-by-side compare (mock)', { tone: 'info' }); }
function onPreview(): void { router.push(`/v/${session.value.id}`); }
function openFind(): void { void modal.open(FindReplaceModal); }

onMounted(() => { document.body.classList.add('has-editor'); });
onUnmounted(() => { document.body.classList.remove('has-editor'); });
</script>

<template>
  <div class="editor" :data-screen-label="`Editor / ${session.id}`">
    <div class="editor__topbar">
      <div class="page-eyebrow" :style="{ marginBottom: '6px' }">
        <RouterLink to="/sessions">Sessions</RouterLink><span class="sep">/</span>
        <RouterLink :to="`/s/${session.id}`">
          <code :style="{ fontFamily: 'var(--font-mono)', color: 'var(--fg-link)' }">{{ session.code || session.id }}</code>
        </RouterLink><span class="sep">/</span>
        <span>Editor</span>
      </div>

      <div class="editor__stepper" role="navigation" aria-label="SOP stages">
        <template v-for="(st, i) in SOP_STAGES" :key="st.id">
          <RouterLink :to="`/e/${session.id}/sop`" :class="stepperCls(i, st.id === session.stage)">
            <span class="dot" /> {{ st.name }}
          </RouterLink>
          <span v-if="i < SOP_STAGES.length - 1" class="editor__stepper-sep">▸</span>
        </template>
        <span :style="{ marginLeft: 'auto', fontSize: '10px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--color-green)' }">
          <Icon name="check" :size="11" /> AI ready
        </span>
      </div>

      <div class="editor__title-row">
        <h1 class="editor__title editor__title--mono">{{ session.code || session.id }}</h1>
        <div class="page-actions">
          <button class="btn btn--ghost btn--sm" data-test-id="editor-result" title="Show last AI result" @click="onResult">
            <Icon name="chevron-left" /> Result
          </button>
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
          <RouterLink :to="`/e/${session.id}/sop`" class="btn btn--ghost btn--sm"><Icon name="branch" /> Workflow</RouterLink>
          <RouterLink :to="`/e/${session.id}/audit`" class="btn btn--ghost btn--sm"><Icon name="history" /> Audit</RouterLink>
          <DownloadMenu :code="session.code || session.id" />
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
        <Icon name="git" /> Discrepancies <span class="count">{{ counts.disc }}</span>
      </button>
      <button :class="['editor__tab', tab === 'audit' ? 'is-active' : '']" role="tab" @click="tab = 'audit'">
        <Icon name="history" /> Audit <span class="count">{{ counts.audit }}</span>
      </button>
      <div class="editor__tab-spacer" />
      <div class="editor__tab-meta"><FlagLegend /></div>
    </div>

    <div class="editor__grid" :style="gridStyle">
      <aside class="editor__leftcol">
        <VideoStrip
          :session="session"
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
        @segment-click="onSegmentClick"
        @word-click="onWordClick"
        @clear-focus="focusedSlideId = null"
        @drop-on-segment="handleDropOnSegment"
        @remove-anchor="handleRemoveAnchor"
      />
      <STTPane
        v-else-if="tab === 'stt'"
        :segments="SEGMENTS"
        :active-segment-id="activeSegment?.id"
        :active-word-idx="activeWordIdx"
        :focused-slide-id="focusedSlideId"
        :slide-rail-mode="slideRailMode"
        @segment-click="onSegmentClick"
        @word-click="onWordClick"
        @clear-focus="focusedSlideId = null"
      />
      <DiscrepanciesPane
        v-else-if="tab === 'disc'"
        :active-segment-id="activeSegment?.id"
        :focused-slide-id="focusedSlideId"
        :slide-rail-mode="slideRailMode"
        @segment-click="onSegmentClick"
        @clear-focus="focusedSlideId = null"
      />
      <AuditTabInline
        v-else
        :session="session"
        :active-segment-id="activeSegment?.id"
        @segment-click="onSegmentClick"
      />

      <div class="editor__resizer" title="Drag to resize" @mousedown="onResizeRight" />

      <STTSidePanel
        v-if="tab === 'stt'"
        :time="time"
        :total-duration="TOTAL_DURATION"
        :segments="SEGMENTS"
      />
      <aside v-else class="rightrail" aria-label="Side panel" data-screen-label="Right Rail">
        <ActiveSlideCard
          :slide="activeSlide"
          :segment-count="segmentsBySlide.get(activeSlide?.id || '')?.length || 0"
          :collapsed="activeSlideCollapsed"
          :time="time"
          :total-duration="TOTAL_DURATION"
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
      <span class="dot" /> WS connected · 18ms
      <span class="sep" />
      <span>autosave <code>2s ago</code></span>
      <span class="sep" />
      <span>longtasks/min: <code :style="{ color: '#5BE3A4' }">1</code></span>
      <span class="sep" />
      <span>heap: <code>108 MB · flat over 30m</code></span>
      <span class="end">
        <span>shortcut: <code>?</code></span>
        <span class="sep" />
        <span>build <code>v4.0.0-ssot-r2</code></span>
      </span>
    </div>
  </div>
</template>
