<script setup lang="ts">
/**
 * TranscriptPane — verbatim port of editor.jsx::TranscriptPane (453-755).
 * AI Transcript tab body: segment cards with karaoke playhead, inline
 * Edit/Reassign/Speaker modes, drop targets for chat/poll anchors, and
 * the rich edit toolbar (B/I/U/list/marks/link/poll-ref).
 */
import { ref, computed, watch, nextTick, useTemplateRef } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import SegmentText from '@/components/editor/SegmentText.vue';
import AnchorBlock from '@/components/editor/AnchorBlock.vue';
import {
  slideAccent,
  speakerDisplay,
  type Slide,
  type Segment,
  type SpeakerDisplay,
} from '@/fixtures/transcript';
import type { ChatMessage, Poll } from '@/fixtures/chat_polls';
import { fmtTime } from '@/utils/editorHelpers';

type AnchorEntry = (ChatMessage & { kind: 'chat' }) | (Poll & { kind: 'poll' });

interface LiveSpeaker {
  id: string;
  short: string | null;
  name: string | null;
  role: string | null;
  avatar_color: string | null;
}

// L2 word-alignment row: one entry per Gemini word in a segment. Matched
// rows carry real STT timestamps (`s`, `e` in ms); unmatched rows carry
// nulls so SegmentText can render the word without data-ws/data-we and
// the time watcher below skips over it.
interface AlignmentEntry { g: number; s: number | null; e: number | null; k: 'exact' | 'unmatched'; }

const props = defineProps<{
  segments: readonly Segment[];
  activeSegmentId: string | null | undefined;
  activeWordIdx: number;
  focusedSlideId: string | null;
  slideRailMode: 'focus' | 'filter';
  anchorsBySegment: Map<string, AnchorEntry[]>;
  // When present, the Speaker picker uses live session speakers instead of
  // the fixture 3-speaker dict. EditorView passes this from the
  // /v1/sessions/{id}/speakers endpoint.
  liveSpeakers?: readonly LiveSpeaker[];
  // When present, slide title/number lookups use real session slides instead
  // of the fixture 24-slide list. Required for segments with real DB UUIDs;
  // without it every segment shows "Unassigned" in the header.
  liveSlides?: readonly Slide[];
  // L2 word-highlight alignment keyed by segment_id. Each value is a
  // positional array (index N = Nth Gemini word per seg.text.split()).
  // SegmentText renders Gemini words as <span class="dw" data-ws data-we>
  // for matched rows; unmatched rows render without data attrs and the
  // watcher below passes through them in zero time.
  liveAlignment?: Map<string, readonly AlignmentEntry[]>;
  time?: number;
}>();

// Real slides only — no fixture fallback. If liveSlides isn't passed, slide
// lookups return undefined and the template falls back to "—" / "Unassigned"
// labels, which is honest empty state.
const slidesById = computed<Map<string, Slide>>(() => {
  const m = new Map<string, Slide>();
  (props.liveSlides ?? []).forEach((s) => m.set(s.id, s));
  return m;
});
function slideById(slideId: string | null | undefined): Slide | undefined {
  if (!slideId) return undefined;
  return slidesById.value.get(slideId);
}
const slidesForReassign = computed<readonly Slide[]>(() => props.liveSlides ?? []);

const emit = defineEmits<{
  (e: 'segmentClick', id: string): void;
  (e: 'wordClick', segId: string, w: number): void;
  (e: 'clearFocus'): void;
  (e: 'dropOnSegment', itemId: string, segId: string): void;
  (e: 'removeAnchor', id: string): void;
  (e: 'editSegment', segId: string, before: string, after: string): void;
  (e: 'reassignSegment', segId: string, beforeSlide: string | null, afterSlide: string): void;
  (e: 'reassignSpeakerLive', segId: string, beforeSpeakerId: string | null, afterSpeakerId: string): void;
}>();

interface InlineEdit {
  segId: string;
  mode: 'edit' | 'reassign' | 'speaker';
  draft?: string;
  draftSpeakerId?: string;
  history?: string[];
  redo?: string[];
}

const inline = ref<InlineEdit | null>(null);
const scrollRef = useTemplateRef<HTMLElement>('scrollRef');
const textareaRef = useTemplateRef<HTMLTextAreaElement>('textareaRef');

const visible = computed<readonly Segment[]>(() => {
  if (props.slideRailMode === 'filter' && props.focusedSlideId) {
    return props.segments.filter((s) => s.slide_id === props.focusedSlideId);
  }
  return props.segments;
});

watch(
  () => props.activeSegmentId,
  async (id) => {
    if (!id || !scrollRef.value) return;
    await nextTick();
    const el = scrollRef.value.querySelector(`[data-seg-id="${id}"]`) as HTMLElement | null;
    if (!el) return;
    const box = scrollRef.value.getBoundingClientRect();
    const eb = el.getBoundingClientRect();
    if (eb.top < box.top + 60 || eb.bottom > box.bottom - 60) {
      scrollRef.value.scrollTo({ top: el.offsetTop - 80, behavior: 'smooth' });
    }
  }
);

function startEdit(seg: Segment): void {
  inline.value = {
    segId: seg.id,
    mode: 'edit',
    draft: `**${speakerDisplay(seg).short}:** ${seg.text}`,
    history: [],
    redo: [],
  };
}
function startReassign(seg: Segment): void {
  inline.value = { segId: seg.id, mode: 'reassign' };
}
function startSpeaker(seg: Segment): void {
  inline.value = { segId: seg.id, mode: 'speaker', draftSpeakerId: seg.speaker_id ?? undefined };
}
function closeInline(): void { inline.value = null; }

// Phase C.3: inline saves now emit up to EditorView which calls the corrections
// API. Live speakers (real UUIDs from the session_speakers roster) go through
// reassignSpeakerLive; fixture-key picks fall back to a warn toast since they
// aren't a backend-resolvable speaker id.
function saveEdit(seg: Segment): void {
  if (!inline.value) return;
  // Strip the speaker prefix the editor injects ("**Short:** text").
  const raw = inline.value.draft || '';
  const stripped = raw.replace(/^\*\*[^*]+:\*\*\s*/, '');
  if (stripped !== seg.text) {
    emit('editSegment', seg.id, seg.text, stripped);
  }
  closeInline();
}
function saveReassign(seg: Segment, slideId: string): void {
  if (slideId !== seg.slide_id) {
    emit('reassignSegment', seg.id, seg.slide_id, slideId);
  }
  closeInline();
}
function saveSpeakerLive(seg: Segment, speakerId: string): void {
  if (speakerId !== seg.speaker_id) {
    emit('reassignSpeakerLive', seg.id, seg.speaker_id ?? null, speakerId);
  }
  closeInline();
}

function mutate(next: string, sel?: { start: number; end: number } | null): void {
  if (!inline.value) return;
  inline.value = {
    ...inline.value,
    draft: next,
    history: [...(inline.value.history || []), inline.value.draft || ''],
    redo: [],
  };
  requestAnimationFrame(() => {
    const ta = textareaRef.value;
    if (!ta) return;
    ta.focus();
    if (sel) { ta.selectionStart = sel.start; ta.selectionEnd = sel.end; }
  });
}

function tbWrap(before: string, after = before): void {
  const ta = textareaRef.value;
  if (!ta || !inline.value) return;
  const s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
  const sel = v.slice(s, e) || 'text';
  const next = v.slice(0, s) + before + sel + after + v.slice(e);
  mutate(next, { start: s + before.length, end: s + before.length + sel.length });
}
function tbLine(prefix: string): void {
  const ta = textareaRef.value;
  if (!ta || !inline.value) return;
  const s = ta.selectionStart, v = ta.value;
  const lineStart = v.lastIndexOf('\n', s - 1) + 1;
  const next = v.slice(0, lineStart) + prefix + v.slice(lineStart);
  mutate(next, { start: s + prefix.length, end: s + prefix.length });
}
function tbInsert(text: string): void {
  const ta = textareaRef.value;
  if (!ta || !inline.value) return;
  const s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
  const next = v.slice(0, s) + text + v.slice(e);
  mutate(next, { start: s + text.length, end: s + text.length });
}
function tbUndo(): void {
  if (!inline.value?.history?.length) return;
  const last = inline.value.history[inline.value.history.length - 1]!;
  inline.value = {
    ...inline.value,
    draft: last,
    history: inline.value.history.slice(0, -1),
    redo: [...(inline.value.redo || []), inline.value.draft || ''],
  };
}
function tbRedo(): void {
  if (!inline.value?.redo?.length) return;
  const next = inline.value.redo[inline.value.redo.length - 1]!;
  inline.value = {
    ...inline.value,
    draft: next,
    history: [...(inline.value.history || []), inline.value.draft || ''],
    redo: inline.value.redo.slice(0, -1),
  };
}
function tbClearMarks(): void {
  if (!inline.value) return;
  const ta = textareaRef.value;
  const cleared = (inline.value.draft || '').replace(/\{\{(uncertain|verified|drift):([^}]+)\}\}/g, '$2');
  mutate(cleared, ta ? { start: ta.selectionStart, end: ta.selectionEnd } : null);
}
function tbLink(): void {
  const url = window.prompt('URL:', 'https://');
  if (url) tbWrap('[', `](${url})`);
}

function segClass(seg: Segment): string {
  const cls = ['segment'];
  if (seg.id === props.activeSegmentId) cls.push('is-active');
  if (props.slideRailMode === 'focus' && seg.slide_id === props.focusedSlideId) cls.push('is-focused-slide');
  if (seg.needs_review) cls.push('is-needs-review');
  if (inline.value?.segId === seg.id) cls.push('is-editing');
  return cls.join(' ');
}

function onDragOver(e: DragEvent): void {
  e.preventDefault();
  (e.currentTarget as HTMLElement).classList.add('is-drop-target');
}
function onDragLeave(e: DragEvent): void {
  (e.currentTarget as HTMLElement).classList.remove('is-drop-target');
}
function onDrop(e: DragEvent, segId: string): void {
  e.preventDefault();
  (e.currentTarget as HTMLElement).classList.remove('is-drop-target');
  const data = e.dataTransfer?.getData('application/vnd.mic.anchor');
  if (data) emit('dropOnSegment', data, segId);
}

interface SpeakerPickRow {
  key: string;                   // real speaker UUID
  short: string;
  name: string;
  color: string;
  role: string;
}

function speakersList(): SpeakerPickRow[] {
  // Real session speakers only — no fixture fallback. If a session has no
  // speakers attached (manifest parse produced none and AI mode didn't
  // detect any), the picker just shows an empty list and the operator can
  // add a speaker via Settings → Team & roles or the SpeakersPanel.
  return (props.liveSpeakers ?? []).map((s, i): SpeakerPickRow => ({
    key:   s.id,
    short: s.short || s.name || 'Speaker',
    name:  s.name  || s.short || 'Speaker',
    color: s.avatar_color || ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626', '#0891b2', '#6366f1', '#ea580c', '#0d9488', '#be185d'][i % 10]!,
    role:  s.role  || '',
  }));
}

function speakerInitials(short: string): string {
  return short.split(' ').map((s) => s[0] || '').join('').slice(0, 2).toUpperCase();
}

function segSpeaker(seg: Segment): SpeakerDisplay {
  return speakerDisplay(seg);
}

function rows(): number {
  const d = inline.value?.draft || '';
  return Math.max(3, Math.ceil(d.length / 90));
}

// Real-time per-word highlight watcher. Ported from MIC's
// mic/frontend/src/views/EditorView.vue:3147-3185. Walks the active
// segment's <span class="dw" data-ws data-we> nodes looking for one whose
// [ws,we] window contains the current playback time, then toggles
// .dw-active. The early-out check (prev-still-in-window) makes the common
// case O(1); only crossing a word boundary triggers a span scan.
//
// Word-span cache (Phase 4 of the 2026-05-23 perf plan). Boundary crossings
// were doing a fresh document.querySelector + root.querySelectorAll every
// time. Cache the spans per segment-id; verify the cached entry is still
// connected on lookup (drops it on segment re-render or unmount).
let prevActiveWordEl: HTMLElement | null = null;
const spanCache = new Map<string, HTMLElement[]>();

function _getSpansForSegment(segId: string): HTMLElement[] | null {
  const cached = spanCache.get(segId);
  if (cached && cached.length > 0 && cached[0]!.isConnected) return cached;
  const root = document.querySelector(`[data-segid="${segId}"]`);
  if (!root) { spanCache.delete(segId); return null; }
  const spans = Array.from(root.querySelectorAll<HTMLElement>('.dw[data-ws]'));
  spanCache.set(segId, spans);
  return spans;
}

watch(() => props.time, (t) => {
  if (t == null || !props.activeSegmentId) return;
  if (prevActiveWordEl?.isConnected) {
    const pws = parseFloat(prevActiveWordEl.dataset.ws ?? '');
    const pwe = parseFloat(prevActiveWordEl.dataset.we ?? '');
    if (!Number.isNaN(pws) && !Number.isNaN(pwe) && t >= pws && t <= pwe) return;
    prevActiveWordEl.classList.remove('dw-active');
    prevActiveWordEl = null;
  }
  const spans = _getSpansForSegment(props.activeSegmentId);
  if (!spans) return;
  for (const el of spans) {
    const ws = parseFloat(el.dataset.ws ?? '');
    const we = parseFloat(el.dataset.we ?? '');
    if (!Number.isNaN(ws) && !Number.isNaN(we) && t >= ws && t <= we) {
      el.classList.add('dw-active');
      prevActiveWordEl = el;
      return;
    }
  }
}, { flush: 'post' });

// Drop the cache entry when the active segment changes so a previously-
// cached but now-edited segment doesn't return stale spans on next visit.
watch(() => props.activeSegmentId, (id, prev) => {
  if (prev && prev !== id) spanCache.delete(prev);
});
</script>

<template>
  <section
    ref="scrollRef"
    class="transcript"
    role="region"
    aria-label="Transcript"
    data-screen-label="Transcript"
  >
    <div v-if="slideRailMode === 'filter' && focusedSlideId" class="transcript__filter-banner" role="status">
      <Icon name="filter" :size="14" />
      <span><strong>Filter mode:</strong> showing {{ visible.length }} segments on slide {{ focusedSlideId.replace('s', '') }}.</span>
      <button class="btn btn--tertiary btn--sm" @click="emit('clearFocus')">Clear filter</button>
    </div>

    <template v-for="seg in visible" :key="seg.id">
      <article
        :data-seg-id="seg.id"
        :class="segClass(seg)"
        :style="{ boxShadow: `inset 3px 0 0 ${slideAccent(seg.slide_id)}` }"
        @click="emit('segmentClick', seg.id)"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @drop="(e) => onDrop(e as DragEvent, seg.id)"
      >
        <header class="segment__header">
          <span class="segment__slide-chip">
            <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: slideAccent(seg.slide_id) }" />
            <strong>{{ slideById(seg.slide_id || '') ? String(slideById(seg.slide_id || '')!.n).padStart(2, '0') : '—' }}</strong>
            <span :style="{ opacity: 0.5 }">·</span>
            <span :style="{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }">{{ slideById(seg.slide_id || '')?.title || 'Unassigned' }}</span>
          </span>
          <span class="segment__inline-actions">
            <template v-if="!(inline && inline.segId === seg.id)">
              <button class="segment__inline-action" data-test-id="seg-edit" @click.stop="startEdit(seg)">Edit</button>
              <button class="segment__inline-action" data-test-id="seg-reassign" @click.stop="startReassign(seg)">Reassign</button>
              <button class="segment__inline-action" data-test-id="seg-speaker" @click.stop="startSpeaker(seg)">Speaker</button>
            </template>
            <template v-if="inline && inline.segId === seg.id && inline.mode === 'speaker'">
              <span :style="{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '2px 8px', border: '1px solid var(--border-subtle)', borderRadius: '999px', fontSize: '11.5px' }">
                <Icon name="message" :size="10" />
                <strong :style="{ color: segSpeaker(seg).color }">{{ segSpeaker(seg).name.replace(/, DVM.*/, '') }} – VIN</strong>
              </span>
              <button class="segment__inline-action" @click.stop>Edit</button>
              <button class="segment__inline-action segment__inline-action--danger" @click.stop="closeInline">
                <Icon name="x" :size="10" /> Remove
              </button>
            </template>
          </span>
        </header>
        <div class="segment__body">
          <div class="segment__gutter">
            <span class="segment__time">{{ fmtTime(seg.start) }}</span>
            <span
              :class="['segment__speaker-pill', `speaker-${seg.speaker}`]"
              :style="{ background: `${segSpeaker(seg).color}22`, color: segSpeaker(seg).color, borderColor: `${segSpeaker(seg).color}55` }"
            >{{ segSpeaker(seg).short }}</span>
          </div>
          <div class="segment__main">
            <div
              v-if="inline && inline.segId === seg.id && inline.mode === 'edit'"
              class="segment-editor"
            >
              <div class="segment-editor__toolbar" @mousedown.prevent>
                <button type="button" class="segment-editor__btn" title="Bold"          @mousedown.prevent @click="tbWrap('**')"><strong>B</strong></button>
                <button type="button" class="segment-editor__btn" title="Italic"        @mousedown.prevent @click="tbWrap('*')"><em>I</em></button>
                <button type="button" class="segment-editor__btn" title="Underline"     @mousedown.prevent @click="tbWrap('__')"><u>U</u></button>
                <span class="segment-editor__sep" />
                <button type="button" class="segment-editor__btn" title="Bullet list"   @mousedown.prevent @click="tbLine('- ')">•</button>
                <button type="button" class="segment-editor__btn" title="Numbered list" @mousedown.prevent @click="tbLine('1. ')">1.</button>
                <span class="segment-editor__sep" />
                <button type="button" class="segment-editor__btn" title="Undo"          @mousedown.prevent @click="tbUndo">↩</button>
                <button type="button" class="segment-editor__btn" title="Redo"          @mousedown.prevent @click="tbRedo">↪</button>
                <button type="button" class="segment-editor__btn" title="Strikethrough" @mousedown.prevent @click="tbWrap('~~')"><s>S</s></button>
                <span class="segment-editor__sep" />
                <button type="button" class="segment-editor__btn" title="Mark uncertain" @mousedown.prevent @click="tbWrap('{{uncertain:', '}}')"><span :style="{ width: '14px', height: '14px', borderRadius: '50%', background: '#facc15', display: 'inline-block' }" /></button>
                <button type="button" class="segment-editor__btn" title="Mark verified"  @mousedown.prevent @click="tbWrap('{{verified:', '}}')"><span :style="{ width: '14px', height: '14px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }" /></button>
                <button type="button" class="segment-editor__btn" title="Mark drift"     @mousedown.prevent @click="tbWrap('{{drift:', '}}')"><span :style="{ width: '14px', height: '14px', borderRadius: '50%', background: '#3b82f6', display: 'inline-block' }" /></button>
                <button type="button" class="segment-editor__btn" title="Clear marks"    @mousedown.prevent @click="tbClearMarks"><span :style="{ width: '14px', height: '14px', borderRadius: '50%', background: '#f9a8d4', display: 'inline-block' }" /></button>
                <span class="segment-editor__sep" />
                <button type="button" class="segment-editor__btn" title="Insert link"           @mousedown.prevent @click="tbLink"><Icon name="anchor" :size="12" /></button>
                <button type="button" class="segment-editor__btn" title="Insert poll reference" @mousedown.prevent @click="tbInsert(' {{poll}}')"><Icon name="list" :size="12" /></button>
              </div>
              <textarea
                ref="textareaRef"
                class="segment-editor__textarea"
                :value="inline.draft"
                wrap="soft"
                :style="{ width: '100%' }"
                :rows="rows()"
                @input="(e) => mutate((e.target as HTMLTextAreaElement).value)"
                @click.stop
              />
              <div class="segment-editor__foot">
                <button class="btn btn--secondary btn--sm" @click.stop="closeInline">Cancel</button>
                <button class="btn btn--sm" :style="{ background: 'var(--color-green)', color: '#fff' }" @click.stop="saveEdit(seg)">Save</button>
              </div>
            </div>
            <div
              v-else-if="inline && inline.segId === seg.id && inline.mode === 'reassign'"
              class="segment-reassign"
            >
              <button
                v-for="sl in slidesForReassign"
                :key="sl.id"
                :class="['segment-reassign__tile', sl.id === seg.slide_id ? 'is-current' : '']"
                @click.stop="saveReassign(seg, sl.id)"
              >
                <span class="segment-reassign__dot" :style="{ background: slideAccent(sl.id) }" />
                <strong>{{ String(sl.n).padStart(2, '0') }}</strong>
                <span :style="{ opacity: 0.4 }">·</span>
                <span class="segment-reassign__title">{{ sl.title.replace(/^(Title — |Case Study \d+ — )/, '') }}</span>
              </button>
              <div :style="{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }">
                <button class="btn btn--secondary btn--sm" @click.stop="closeInline">Cancel</button>
              </div>
            </div>
            <div
              v-else-if="inline && inline.segId === seg.id && inline.mode === 'speaker'"
              class="segment-speakerpick"
            >
              <button
                v-for="row in speakersList()"
                :key="row.key"
                :class="['segment-speakerpick__tile', row.key === (seg.speaker_id || inline.draftSpeakerId) ? 'is-current' : '']"
                @click.stop="saveSpeakerLive(seg, row.key)"
              >
                <span class="segment-speakerpick__avatar" :style="{ background: row.color }">{{ speakerInitials(row.short) }}</span>
                <div>
                  <div :style="{ fontWeight: 700, fontSize: '12.5px' }">{{ row.name }}</div>
                  <div :style="{ fontSize: '11px', color: 'var(--fg2)' }">{{ row.role }}</div>
                </div>
              </button>
              <div :style="{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }">
                <button class="btn btn--secondary btn--sm" @click.stop="closeInline">Cancel</button>
              </div>
            </div>
            <template v-else>
              <SegmentText
                :data-segid="seg.id"
                :text="seg.text"
                :flags="seg.ai_flags"
                :active-word-idx="seg.id === activeSegmentId ? activeWordIdx : -1"
                :live-alignment="liveAlignment?.get(seg.id)"
                @word-click="(w) => emit('wordClick', seg.id, w)"
              />
              <div class="segment__chiprow">
                <span
                  v-if="seg.needs_review"
                  class="segment__chip"
                  :style="{ background: 'rgba(183,93,4,0.10)', color: 'var(--color-amber)', borderColor: 'rgba(183,93,4,0.3)' }"
                ><Icon name="flag" /> needs review</span>
                <span
                  v-if="seg.confidence === 'low'"
                  class="segment__chip"
                  :style="{ background: 'rgba(8,97,206,0.08)', color: 'var(--color-blue)', borderColor: 'rgba(8,97,206,0.25)' }"
                ><Icon name="alert" /> low confidence</span>
                <span
                  v-if="seg.ai_flags.length > 0"
                  class="segment__chip"
                  :style="{ background: 'rgba(197,70,68,0.06)', color: 'var(--color-red)', borderColor: 'rgba(197,70,68,0.25)' }"
                ><Icon name="lightning" /> {{ seg.ai_flags.length }} AI flag{{ seg.ai_flags.length === 1 ? '' : 's' }}</span>
                <span
                  v-if="seg.has_user_override"
                  class="segment__chip"
                  :style="{ background: 'rgba(0,40,85,0.08)', color: 'var(--color-navy)' }"
                ><Icon name="edit" /> user override</span>
              </div>
            </template>
          </div>
        </div>
      </article>
      <AnchorBlock
        v-for="a in (anchorsBySegment.get(seg.id) || [])"
        :key="a.id"
        :item="a as any"
        :kind="a.kind"
        :slide="slideById(seg.slide_id || '')"
        @remove="(id) => emit('removeAnchor', id)"
      />
    </template>
    <div :style="{ padding: '24px 12px', textAlign: 'center', color: 'var(--fg2)', fontSize: '12px' }">
      End of transcript · {{ visible.length }} segments rendered (virtualized)
    </div>
  </section>
</template>
