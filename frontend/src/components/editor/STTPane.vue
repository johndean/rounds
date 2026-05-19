<script setup lang="ts">
/**
 * STTPane — verbatim port of editor.jsx::STTPane (760-886).
 * STT reference tab body: monospace lowercase tokens with timing superscripts,
 * filler tokens, drift highlights, scrolls to active segment.
 */
import { computed, watch, nextTick, useTemplateRef } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { slideAccent, slideById, type Segment } from '@/fixtures/transcript';
import { DISCREPANCIES } from '@/fixtures/audit';
import type { WordRow } from '@/services/api';
import { withAlpha, fmtTime } from '@/utils/editorHelpers';

interface Token { kind: 'filler' | 'drift' | null; text: string; t: number; confidence?: number; }

const props = withDefaults(defineProps<{
  segments: readonly Segment[];
  activeSegmentId: string | null | undefined;
  activeWordIdx: number;
  focusedSlideId: string | null;
  slideRailMode: 'focus' | 'filter';
  // AI MODE direct: the session is `ready` before Cloud STT finishes. The
  // STT Raw tab shows "processing in background" until the WS `stt_ready`
  // event arrives. Defaults preserve old behavior (always-ready) for
  // standard / enhanced pipelines that finish STT before the editor opens.
  sttReady?: boolean;
  sttFailed?: boolean;
  // Real Google STT data grouped by segment_id. When this Map has entries
  // for the active segments, STTPane renders real per-word tokens with
  // real timestamps + confidence (no fake fillers, no fixture drift).
  // Falls through to the fixture demo path when the Map is empty/undefined.
  liveWords?: Map<string, WordRow[]>;
}>(), {
  sttReady: true,
  sttFailed: false,
  liveWords: () => new Map(),
});

// True when we have any real STT word rows attached to current segments.
// Drives the entire fakes-vs-real decision below.
const hasLiveWords = computed<boolean>(() => {
  if (!props.liveWords || props.liveWords.size === 0) return false;
  return props.segments.some((s) => (props.liveWords!.get(s.id)?.length ?? 0) > 0);
});

const emit = defineEmits<{
  (e: 'segmentClick', id: string): void;
  (e: 'wordClick', segId: string, w: number): void;
  (e: 'clearFocus'): void;
}>();

const scrollRef = useTemplateRef<HTMLElement>('scrollRef');

const visible = computed<Segment[]>(() => {
  if (props.slideRailMode === 'filter' && props.focusedSlideId) {
    return props.segments.filter((s) => s.slide_id === props.focusedSlideId);
  }
  return [...props.segments];
});

const sttBySegId = computed<Map<string, Token[]>>(() => {
  const m = new Map<string, Token[]>();
  // ─── REAL path: render actual Google STT tokens ───────────────────────
  if (hasLiveWords.value) {
    props.segments.forEach((seg) => {
      const ws = props.liveWords!.get(seg.id) || [];
      m.set(seg.id, ws.map((w): Token => ({
        kind: null,
        text: w.word.toLowerCase(),
        t:    +(w.start_ms / 1000).toFixed(2),
        confidence: w.confidence,
      })));
    });
    return m;
  }
  // ─── FIXTURE-DEMO path: prototype with hardcoded fillers + fixture drift.
  // Only reached when liveWords is empty AND we're on the fixture seg ids
  // (live sessions with no STT yet show the spinner / "no words" banner
  // below, so we don't fall through here for them).
  const drift = new Map(DISCREPANCIES.map((d) => [d.seg, d]));
  const fillers = ['um', 'uh', 'you know', 'like'];
  props.segments.forEach((seg, i) => {
    const words = seg.text.toLowerCase().replace(/[.,;!?—–]/g, '').split(/\s+/);
    const tokens: Token[] = [];
    const dur = Math.max(0.1, seg.end - seg.start);
    const perWord = dur / words.length;
    const drow = drift.get(seg.id);
    if (i % 4 === 0) {
      tokens.push({ kind: 'filler', text: fillers[i % fillers.length]!, t: seg.start });
    }
    words.forEach((w, j) => {
      let kind: Token['kind'] = null;
      let text = w;
      if (drow && drow.kind === 'drift') {
        const baseFirstWord = drow.base.toLowerCase().split(/\s+/)[0];
        if (w === baseFirstWord) {
          text = drow.stt.toLowerCase().split(/\s+/).join(' ');
          kind = 'drift';
        }
      }
      tokens.push({ kind, text, t: +(seg.start + j * perWord).toFixed(2) });
    });
    m.set(seg.id, tokens);
  });
  return m;
});

// True when we're on a live session (real UUID segments) but no STT words
// arrived yet. Used to render an honest "STT not available" banner instead
// of falling through to the fixture-demo fake-filler render.
const isLiveSessionWithoutWords = computed<boolean>(() => {
  if (hasLiveWords.value) return false;
  if (!props.segments.length) return false;
  return !/^seg_\d{3}$/.test(props.segments[0]!.id);
});

watch(
  () => props.activeSegmentId,
  async (id) => {
    if (!id || !scrollRef.value) return;
    await nextTick();
    const el = scrollRef.value.querySelector(`[data-stt-seg="${id}"]`) as HTMLElement | null;
    if (!el) return;
    const box = scrollRef.value.getBoundingClientRect();
    const eb = el.getBoundingClientRect();
    if (eb.top < box.top + 60 || eb.bottom > box.bottom - 60) {
      scrollRef.value.scrollTo({ top: el.offsetTop - 80, behavior: 'smooth' });
    }
  }
);

interface TokenView { kind: Token['kind']; text: string; t: number; cls: string; idx: number; }

function buildTokenViews(seg: Segment): TokenView[] {
  const tokens = sttBySegId.value.get(seg.id) || [];
  const out: TokenView[] = [];
  const isActive = seg.id === props.activeSegmentId;
  let nonFillerCount = -1;
  tokens.forEach((tok) => {
    if (tok.kind === 'filler') {
      out.push({ ...tok, cls: 'stt-token stt-token--filler', idx: -1 });
      return;
    }
    nonFillerCount++;
    const cls = ['stt-token'];
    if (tok.kind === 'drift') cls.push('stt-token--drift');
    if (isActive && nonFillerCount === props.activeWordIdx) cls.push('is-current');
    out.push({ ...tok, cls: cls.join(' '), idx: nonFillerCount });
  });
  return out;
}

function segCls(seg: Segment): string {
  return seg.id === props.activeSegmentId ? 'stt-segment is-active' : 'stt-segment';
}
function confLabel(seg: Segment): string {
  // Real per-segment average confidence when we have live STT words.
  if (hasLiveWords.value) {
    const ws = props.liveWords!.get(seg.id) || [];
    if (ws.length === 0) return 'conf —';
    const avg = ws.reduce((a, w) => a + w.confidence, 0) / ws.length;
    return `conf ${avg.toFixed(2)}`;
  }
  // Fixture-demo fallback: deterministic-by-index value (cosmetic, demo only).
  return seg.confidence === 'low' ? 'conf 0.61' : `conf 0.${82 + (seg.idx % 14)}`;
}
function confSecondStyle(accent: string): Record<string, string> {
  return { fontFamily: 'var(--font-mono)', color: accent, borderColor: withAlpha(accent, '44') };
}
</script>

<template>
  <section
    ref="scrollRef"
    class="stt-pane"
    aria-label="STT reference"
    data-screen-label="STT Reference"
  >
    <!-- Background-STT placeholder (MIC parity: ai_process completes first,
         editor opens immediately, stt_background_task runs in parallel and
         emits stt_ready when done). -->
    <div
      v-if="!sttReady && !sttFailed"
      class="stt-pane__loading"
      role="status"
      :style="{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: '12px', padding: '60px 24px', color: 'var(--fg2)',
        fontSize: '13px', fontFamily: 'var(--font-family)', textAlign: 'center'
      }"
    >
      <div
        :style="{
          width: '18px', height: '18px', borderRadius: '50%',
          border: '2px solid rgba(255,255,255,0.15)', borderTopColor: '#2563eb',
          animation: 'stt-spin 0.8s linear infinite'
        }"
      />
      <span>Speech-to-text processing in background.</span>
    </div>

    <div
      v-else-if="sttFailed"
      class="stt-pane__failed"
      role="status"
      :style="{
        padding: '40px 24px', textAlign: 'center', color: 'var(--color-red)',
        fontSize: '13px', fontFamily: 'var(--font-family)'
      }"
    >
      <Icon name="alert" :size="16" />
      <div :style="{ marginTop: '8px' }">
        STT processing failed — the AI transcript above is your primary source.
      </div>
    </div>

    <template v-else>

    <!-- LIVE-SESSION WITHOUT WORDS: stt_background hasn't produced rows yet
         (or was killed by a worker restart). Show an honest "no STT data"
         banner instead of rendering fake fillers and AI-text-as-STT. -->
    <div
      v-if="isLiveSessionWithoutWords"
      class="stt-pane__banner"
      role="note"
      :style="{ background: 'rgba(217,119,6,0.10)', borderColor: 'rgba(217,119,6,0.4)', color: 'var(--color-amber)' }"
    >
      <Icon name="alert" :size="16" />
      <div>
        <strong>No STT words for this session yet.</strong>
        Google STT runs in <code :style="{ background: 'rgba(255,255,255,0.08)', padding: '1px 5px', borderRadius: '2px' }">stt_background_task</code>
        after AI-mode upload. If you're seeing this on a session that finished a while ago, the worker may have
        been restarted mid-run. Re-upload the session or wait for stt_background to retry.
      </div>
      <span class="chip" :style="{ background: 'rgba(217,119,6,0.18)', color: '#fff', borderColor: 'rgba(217,119,6,0.5)' }">no data</span>
    </div>

    <!-- LIVE WORDS PRESENT: render real Google STT tokens, real timestamps,
         real per-segment confidence. Banner reflects truth. -->
    <div
      v-else-if="hasLiveWords"
      class="stt-pane__banner"
      role="note"
      :style="{ background: 'rgba(0,125,97,0.10)', borderColor: 'rgba(0,125,97,0.4)', color: 'var(--color-green)' }"
    >
      <Icon name="alert" :size="16" />
      <div>
        <strong>STT reference · real Google STT.</strong> Per-word tokens with real start-ms timestamps and
        confidence values from Google Speech-to-Text. Used for playback synchronization, word highlighting,
        and discrepancy classification. Read-only — these tokens never appear in
        <code :style="{ background: 'rgba(255,255,255,0.08)', padding: '1px 5px', borderRadius: '2px' }">base_text</code>
        and never participate in correction lineage.
      </div>
      <span class="chip" :style="{ background: 'rgba(0,125,97,0.18)', color: '#fff', borderColor: 'rgba(0,125,97,0.5)' }">live</span>
    </div>

    <!-- FIXTURE-DEMO path (prototype.html): original blue banner kept verbatim. -->
    <div v-else class="stt-pane__banner" role="note">
      <Icon name="alert" :size="16" />
      <div>
        <strong>STT reference · orthogonal pipeline.</strong> Raw Google STT tokens used only for playback
        synchronization, word highlighting, and discrepancy classification. These tokens <em>never</em> appear
        in <code :style="{ background: 'rgba(255,255,255,0.08)', padding: '1px 5px', borderRadius: '2px' }">base_text</code>,
        never participate in correction lineage, and are never user-editable.
        Verified by pipeline-isolation test · L2.
      </div>
      <span class="chip" :style="{ background: 'rgba(0,151,169,0.18)', color: '#fff', borderColor: 'rgba(0,151,169,0.5)' }">read-only</span>
    </div>

    <div
      v-if="slideRailMode === 'filter' && focusedSlideId"
      class="transcript__filter-banner"
      role="status"
      :style="{ background: 'rgba(0,151,169,0.08)', borderColor: 'rgba(0,151,169,0.35)', color: 'var(--color-teal)' }"
    >
      <Icon name="filter" :size="14" />
      <span><strong>Filter mode:</strong> showing {{ visible.length }} STT segments on slide {{ focusedSlideId.replace('s', '') }}.</span>
      <button class="btn btn--tertiary btn--sm" @click="emit('clearFocus')">Clear filter</button>
    </div>

    <article
      v-for="seg in visible"
      :key="seg.id"
      :data-stt-seg="seg.id"
      :class="segCls(seg)"
      :style="{ boxShadow: `inset 3px 0 0 ${slideAccent(seg.slide_id)}` }"
      @click="emit('segmentClick', seg.id)"
    >
      <div class="stt-segment__gutter">
        <span class="stt-segment__time">{{ fmtTime(seg.start) }}</span>
        <span :class="['stt-segment__conf', seg.confidence === 'low' ? 'low' : '']">{{ confLabel(seg) }}</span>
        <span class="stt-segment__conf" :style="confSecondStyle(slideAccent(seg.slide_id))">
          {{ slideById(seg.slide_id || '') ? `s${String(slideById(seg.slide_id || '')!.n).padStart(2, '0')}` : seg.id }}
        </span>
      </div>
      <div class="stt-segment__main">
        <template v-for="(tok, i) in buildTokenViews(seg)" :key="i">
          <span v-if="tok.kind === 'filler'" :class="tok.cls">[{{ tok.text }}]&nbsp;</span>
          <span
            v-else
            :class="tok.cls"
            @click.stop="emit('wordClick', seg.id, tok.idx)"
          >{{ tok.text }}<span class="t">{{ tok.t.toFixed(1) }}</span>{{ ' ' }}</span>
        </template>
      </div>
    </article>

    <div :style="{ padding: '24px 12px', textAlign: 'center', color: 'rgba(255,255,255,0.4)', fontSize: '11px', fontFamily: 'var(--font-family)' }">
      End of STT stream · {{ visible.length }} segments · superscript = token start (s) · drift highlights match discrepancy classification
    </div>

    </template>
  </section>
</template>

<style scoped>
@keyframes stt-spin { to { transform: rotate(360deg); } }
</style>
