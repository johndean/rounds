<script setup lang="ts">
/**
 * Viewer (Preview) — /v/:id
 * Faithful 1:1 port of docs/port-source/viewer.jsx (146 LOC).
 */
import { computed, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { SESSIONS } from '@/fixtures/sessions';
import { SEGMENTS, SLIDES, SPEAKERS } from '@/fixtures/transcript';
import { toast } from '@/composables/useToast';

const props = defineProps<{ id: string }>();

const session = computed(() => SESSIONS.find(s => s.id === props.id) ?? SESSIONS[0]!);
const segments = SEGMENTS;
const slides = SLIDES;

const segmentsBySlide = computed(() => {
  const m = new Map<string, typeof SEGMENTS[number][]>();
  slides.forEach(sl => m.set(sl.id, []));
  segments.forEach(s => { if (s.slide_id) m.get(s.slide_id)?.push(s); });
  return m;
});

const includeKeyPoints = ref(false);

const downloads = [
  { kind: 'Word Document',  ext: '.docx', desc: 'Macro-compatible transcript with slide codes and speaker labels. Run SRT_Transcript or CMS_Transcript macro to prep for publishing.' },
  { kind: 'Captions',       ext: '.srt',  desc: 'SubRip subtitle file for Wistia or video player caption upload.' },
  { kind: 'Plain Text',     ext: '.txt',  desc: 'Simple text for email, forum paste, or quick reference.' },
  { kind: 'Word Macro',     ext: '.zip',  desc: 'One-time install. Open in Word, Developer, Visual Basic, Import.' },
];

const publishing = [
  { label: 'Zoom recording', href: 'https://vin.zoom.us/s/94555598059' },
  { label: 'Slides',         href: 'https://www.vin.com/members/slideshow/SlideShowData.ashx?ProjectId=35411' },
  { label: 'Podbean',        href: 'https://vincasts.podbean.com/e/wildlife-conservation-translocations-how-zoos-make-decisions-reduce-risk/' },
  { label: 'VINcast',        href: 'https://www.vin.com/doc/?id=13096848' },
  { label: 'Intranet',       href: 'https://www.vin.com/Admin/Intranet/Client.plx?UniqueID=209370' },
  { label: 'Message board',  href: 'https://www.vin.com/doc/?Id=13088616&SAId=2&IsMBLink=1&MyActivities=1' },
  { label: 'Session page',   href: 'https://www.vin.com/doc/?id=12943766' },
];

function downloadFile(ext: string): void {
  toast.push(`Download ${ext.slice(1).toUpperCase()} (mock)`, { tone: 'success' });
}
function openPub(p: { label: string }, e: Event): void {
  e.preventDefault();
  toast.push(`Open ${p.label} (mock)`);
}
</script>

<template>
  <main class="preview-page" data-screen-label="Viewer / Preview">
    <!-- Identity header -->
    <div class="preview-id">
      <div class="preview-id__code">{{ session.code || session.id }}</div>
      <h1 class="preview-id__title">{{ session.title }}</h1>
      <div class="preview-id__interim">INTERIM: {{ session.title.replace(/^.+?: /, '').slice(0, 80) }}</div>
      <div class="preview-id__chips">
        <span class="chip chip--ghost"><strong :style="{ fontWeight: 700 }">CLASS ID</strong> VINR414-0126</span>
        <span class="chip chip--blue">Student</span>
        <span class="chip chip--blue">Veterinary</span>
      </div>
    </div>

    <!-- Export Preview toolbar -->
    <div class="preview-toolbar">
      <div>
        <h2 class="preview-section-title">Export Preview</h2>
      </div>
      <div class="preview-toolbar__actions">
        <label class="preview-toolbar__check">
          <input v-model="includeKeyPoints" type="checkbox" />
          Include key points section
        </label>
        <RouterLink :to="`/e/${session.id}`" class="btn btn--secondary"><Icon name="chevron-left" /> Editor</RouterLink>
      </div>
    </div>

    <!-- Format cards -->
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

    <!-- Publishing checklist -->
    <div class="preview-checklist">
      <div class="preview-checklist__head">PUBLISHING CHECKLIST</div>
      <div class="preview-checklist__body">
        <div v-for="p in publishing" :key="p.label" class="preview-checklist__row">
          <a :href="p.href" class="preview-checklist__label" @click="openPub(p, $event)">{{ p.label }}</a>
          <code class="preview-checklist__url">{{ p.href }}</code>
        </div>
      </div>
    </div>

    <!-- Per-slide transcript preview cards -->
    <div class="preview-slides">
      <template v-for="sl in slides" :key="sl.id">
        <article
          v-if="(segmentsBySlide.get(sl.id) || []).length > 0 || sl.kind === 'title' || sl.kind === 'bio'"
          class="preview-slide"
        >
          <h3 class="preview-slide__title">Slide {{ sl.n }}</h3>
          <div v-if="sl.kind === 'bio' || sl.kind === 'objectives' || sl.kind === 'title'" class="preview-slide__centered">
            {{ sl.title }}
          </div>
          <div class="preview-slide__body">
            <div v-if="(segmentsBySlide.get(sl.id) || []).length === 0" class="preview-slide__noaudio">( no audio )</div>
            <p v-for="seg in (segmentsBySlide.get(sl.id) || [])" :key="seg.id" class="preview-slide__para">
              <strong>**{{ SPEAKERS[seg.speaker].short.replace(/^Dr\. /, '') }}:**</strong> {{ seg.text }}
            </p>
          </div>
        </article>
      </template>
    </div>

    <div v-if="includeKeyPoints" class="preview-keypoints">
      <h3 class="preview-section-title" :style="{ marginBottom: '14px' }">Key Points</h3>
      <ul :style="{ fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: 1.75, color: 'var(--fg1)', paddingLeft: '20px' }">
        <li>GI foreign body removal is one of the most common soft-tissue surgeries; ~78% canine, ~19% feline incidence.</li>
        <li>Linear FBs are dangerous because of plication — never pull on a linear FB until proximally unanchored.</li>
        <li>Three-criterion resection rule: non-viability, perforation, or {{ '>' }}50% lumen compromise.</li>
        <li>Sublingual exam non-negotiable in every vomiting cat.</li>
        <li>Closure pattern doesn't statistically affect dehiscence rate (~2.8% vs 3.1%, p=0.64).</li>
      </ul>
    </div>

    <div :style="{ padding: '30px 0', textAlign: 'center', fontSize: '11px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)' }">
      End of preview · {{ segments.length }} segments · {{ slides.length }} slides · build v4.0.0-ssot-r2
    </div>
  </main>
</template>
