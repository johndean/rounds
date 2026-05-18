<script setup lang="ts">
/**
 * Viewer (Preview) — /v/:id
 *
 * Same DOM as React viewer.jsx. Wired:
 *   GET /v1/sessions/{id}
 *   GET /v1/sessions/{id}/segments
 *   GET /v1/sessions/{id}/slides
 *   GET /v1/sessions/{id}/speakers
 * Empty state for any not yet populated.
 */
import { computed, onMounted, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { sessions as sessionsApi, segments as segmentsApi, type SessionSummary, type SegmentRow } from '@/services/api';
import { http } from '@/services/http';
import { toast } from '@/composables/useToast';

const props = defineProps<{ id: string }>();

interface SlideRow { id: string; slide_index: number; title: string | null; start_ms: number | null; end_ms: number | null; }
interface SpeakerRow { id: string; name: string | null; short: string | null; role: string | null; }

const session = ref<SessionSummary | null>(null);
const slides = ref<SlideRow[]>([]);
const segments = ref<SegmentRow[]>([]);
const speakers = ref<Record<string, SpeakerRow>>({});
const loading = ref(true);

const includeKeyPoints = ref(false);

onMounted(async () => {
  try {
    const [s, sl, sg, sp] = await Promise.all([
      sessionsApi.get(props.id).catch(() => null),
      http<SlideRow[]>(`/v1/sessions/${encodeURIComponent(props.id)}/slides`).catch(() => []),
      segmentsApi.list(props.id).catch(() => []),
      http<SpeakerRow[]>(`/v1/sessions/${encodeURIComponent(props.id)}/speakers`).catch(() => []),
    ]);
    session.value = s;
    slides.value = sl;
    segments.value = sg;
    const map: Record<string, SpeakerRow> = {};
    for (const row of sp) map[row.id] = row;
    speakers.value = map;
  } finally {
    loading.value = false;
  }
});

const segmentsBySlide = computed(() => {
  const m = new Map<string, SegmentRow[]>();
  slides.value.forEach(sl => m.set(sl.id, []));
  segments.value.forEach(s => {
    if (s.slide_id) {
      const list = m.get(s.slide_id);
      if (list) list.push(s);
    }
  });
  return m;
});

function speakerLabel(speakerId: string | null | undefined): string {
  if (!speakerId) return '';
  const sp = speakers.value[speakerId];
  return (sp?.short || sp?.name || '').replace(/^Dr\. /, '');
}

const downloads = [
  { kind: 'Word Document',  ext: '.docx', desc: 'Macro-compatible transcript with slide codes and speaker labels. Run SRT_Transcript or CMS_Transcript macro to prep for publishing.' },
  { kind: 'Captions',       ext: '.srt',  desc: 'SubRip subtitle file for Wistia or video player caption upload.' },
  { kind: 'Plain Text',     ext: '.txt',  desc: 'Simple text for email, forum paste, or quick reference.' },
  { kind: 'Word Macro',     ext: '.zip',  desc: 'One-time install. Open in Word, Developer, Visual Basic, Import.' },
];

const publishing = [
  { label: 'Zoom recording', href: '#' },
  { label: 'Slides',         href: '#' },
  { label: 'Podbean',        href: '#' },
  { label: 'VINcast',        href: '#' },
  { label: 'Intranet',       href: '#' },
  { label: 'Message board',  href: '#' },
  { label: 'Session page',   href: '#' },
];

function downloadFile(ext: string): void {
  toast.push(`Download ${ext.slice(1).toUpperCase()} — pending exports endpoint`, { tone: 'info' });
}
function openPub(p: { label: string }, e: Event): void {
  e.preventDefault();
  toast.push(`Open ${p.label} (mock)`);
}
</script>

<template>
  <main class="preview-page" data-screen-label="Viewer / Preview">
    <div v-if="loading" :style="{ padding: '60px', textAlign: 'center', color: 'var(--fg2)' }">Loading preview…</div>
    <template v-else>
      <div class="preview-id">
        <div class="preview-id__code">{{ session?.code || props.id }}</div>
        <h1 class="preview-id__title">{{ session?.title || 'Session not found' }}</h1>
        <div v-if="session?.presenter" class="preview-id__interim">{{ session.presenter }}</div>
        <div class="preview-id__chips">
          <span v-for="t in (session?.taxonomy || [])" :key="t" class="chip chip--blue">{{ t }}</span>
        </div>
      </div>

      <div class="preview-toolbar">
        <div><h2 class="preview-section-title">Export Preview</h2></div>
        <div class="preview-toolbar__actions">
          <label class="preview-toolbar__check">
            <input v-model="includeKeyPoints" type="checkbox" />
            Include key points section
          </label>
          <RouterLink v-if="session" :to="`/e/${session.id}`" class="btn btn--secondary"><Icon name="chevron-left" /> Editor</RouterLink>
        </div>
      </div>

      <div class="preview-formats">
        <button
          v-for="d in downloads"
          :key="d.ext"
          class="preview-format"
          :data-test-id="`preview-${d.ext.slice(1)}`"
          @click="downloadFile(d.ext)"
        >
          <div class="preview-format__head">
            <Icon name="download" :size="13" />
            <span class="preview-format__kind">{{ d.kind }}</span>
            <code class="preview-format__ext">{{ d.ext }}</code>
          </div>
          <div class="preview-format__desc">{{ d.desc }}</div>
        </button>
      </div>

      <div class="preview-checklist">
        <div class="preview-checklist__head">PUBLISHING CHECKLIST</div>
        <div class="preview-checklist__body">
          <div v-for="p in publishing" :key="p.label" class="preview-checklist__row">
            <a :href="p.href" class="preview-checklist__label" @click="openPub(p, $event)">{{ p.label }}</a>
            <code class="preview-checklist__url">{{ p.href }}</code>
          </div>
        </div>
      </div>

      <div class="preview-slides">
        <article
          v-for="sl in slides"
          :key="sl.id"
          class="preview-slide"
        >
          <h3 class="preview-slide__title">Slide {{ sl.slide_index + 1 }}</h3>
          <div v-if="sl.title" class="preview-slide__centered">{{ sl.title }}</div>
          <div class="preview-slide__body">
            <div v-if="(segmentsBySlide.get(sl.id) || []).length === 0" class="preview-slide__noaudio">( no audio )</div>
            <p v-for="seg in (segmentsBySlide.get(sl.id) || [])" :key="seg.id" class="preview-slide__para">
              <strong v-if="seg.speaker_id">**{{ speakerLabel(seg.speaker_id) }}:**</strong> {{ seg.text }}
            </p>
          </div>
        </article>
        <div v-if="slides.length === 0" :style="{ padding: '40px 0', textAlign: 'center', color: 'var(--fg2)', fontSize: '13px' }">
          No slides yet — ingest pipeline pending.
        </div>
      </div>

      <div v-if="includeKeyPoints" class="preview-keypoints">
        <h3 class="preview-section-title" :style="{ marginBottom: '14px' }">Key Points</h3>
        <p :style="{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--fg2)' }">
          Key-points extraction runs in the AI MODE Gemini pass. Empty until the session is processed.
        </p>
      </div>

      <div :style="{ padding: '30px 0', textAlign: 'center', fontSize: '11px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)' }">
        End of preview · {{ segments.length }} segments · {{ slides.length }} slides · build v4.0.0-ssot-r2
      </div>
    </template>
  </main>
</template>
