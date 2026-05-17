<script setup lang="ts">
/**
 * Session Detail — /s/:id
 * Faithful 1:1 port of docs/port-source/session-detail.jsx (305 LOC).
 */
import { computed } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { SESSIONS } from '@/fixtures/sessions';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import { SEGMENTS, SLIDES, TOTAL_DURATION, slideAccent } from '@/fixtures/transcript';
import { toast } from '@/composables/useToast';

const props = defineProps<{ id: string }>();

const session = computed(() => SESSIONS.find(s => s.id === props.id) ?? SESSIONS[0]!);
const stages = SOP_STAGES;
const segments = SEGMENTS;
const slides = SLIDES;

const segmentsBySlide = computed(() => {
  const m = new Map<string, typeof SEGMENTS[number][]>();
  slides.forEach(sl => m.set(sl.id, []));
  segments.forEach(s => { if (s.slide_id) m.get(s.slide_id)?.push(s); });
  return m;
});

const stageAssignments = [
  { stage: 'copy_draft', who: '(unassigned)',                  group: false, faded: true },
  { stage: 'medical',    who: 'V@V · Heather Howell',           group: false, faded: false },
  { stage: 'copy_final', who: 'Main Contact · Ruth Schoonover', group: false, faded: false },
  { stage: 'cms',        who: 'Content Team (default)',         group: true,  faded: false },
  { stage: 'captions',   who: 'Content Team',                   group: false, faded: false },
  { stage: 'qa',         who: 'Content Team (default)',         group: true,  faded: false },
];

const sessionFiles = [
  { name: 'Slides',           present: true,  desc: 'Slides extracted — you can replace or append a new deck.', icon: 'slide' },
  { name: 'Chat log',         present: true,  desc: 'Chat present — uploading new chat replaces existing messages.', icon: 'message' },
  { name: 'Session manifest', present: true,  desc: 'Manifest present — you can use a new one or keep current.', icon: 'doc' },
  { name: 'Speaker bios',     present: false, desc: "Without bios, speaker credentials won't render in the export.", icon: 'user' },
];

const publishingLinks = ['Zoom recording', 'Slides', 'Podbean', 'VINcast', 'Intranet', 'Session page'];
const downloads = [
  { kind: 'Word Document',  ext: '.docx', desc: 'Macro-compatible transcript with slide codes and speaker labels.' },
  { kind: 'Captions',       ext: '.srt',  desc: 'SubRip subtitle file for Wistia or video player.' },
  { kind: 'Plain Text',     ext: '.txt',  desc: 'Simple text for email, forum paste, or quick reference.' },
  { kind: 'Word Macro',     ext: '.zip',  desc: 'One-time install. Developer → Visual Basic → Import.' },
];

const reviewQueue = computed(() => segments
  .filter(s => s.needs_review).slice(0, 10).map((s, i) => ({
    id: `g${95 + i}`,
    seg: s.id,
    conf: s.confidence === 'low' ? 0 : 0,
    preview: s.text.slice(0, 80) + '…',
    assignee: 'unassigned',
  })));

const totalSegs = computed(() => session.value.segs || segments.length);

const segConfList = computed(() => {
  const total = Math.min(31, totalSegs.value);
  return Array.from({ length: total }, (_, i) => {
    const pct = 75 + ((i * 7) % 25);
    const slideId = slides[i % slides.length]?.id ?? null;
    return { n: i + 1, conf: pct, ok: pct >= 80 ? 'ok' : 'warn', slideColor: slideAccent(slideId) };
  });
});

function downloadFile(ext: string): void {
  toast.push(`Download ${ext.slice(1).toUpperCase()} (mock)`, { tone: 'success' });
}
function reassignStage(name: string): void { toast.push(`Reassign ${name} — picker (mock)`); }
function fileAction(f: typeof sessionFiles[number]): void {
  toast.push(`${f.present ? 'Update' : 'Add'} ${f.name} — file picker (mock)`);
}
function pubLink(p: string): void { toast.push(`${p} — link saved (mock)`, { tone: 'success' }); }
</script>

<template>
  <main class="page" :data-screen-label="`Session Detail / ${session.id}`">
    <div class="page-eyebrow">
      <RouterLink to="/sessions">Sessions</RouterLink>
      <span class="sep">/</span>
      <code :style="{ fontFamily: 'var(--font-mono)', color: 'var(--fg-link)' }">{{ session.code || session.id }}</code>
    </div>

    <!-- Header strip -->
    <div class="sd-header">
      <div>
        <div :style="{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '6px' }">
          <span class="chip chip--green"><Icon name="check" :size="10" /> Content ready</span>
          <span class="chip chip--ghost">{{ session.code || session.id }}</span>
        </div>
        <h1 class="sd-header__title">{{ session.title }}</h1>
        <p class="sd-header__sub">INTERIM: {{ session.title }}</p>
      </div>
      <div class="sd-header__actions">
        <span class="chip chip--amber"><span class="chip__dot" /> {{ session.needsReviewCount || 0 }} to review</span>
        <span class="chip chip--green"><span class="chip__dot" /> {{ session.alignment || 100 }}% aligned</span>
        <RouterLink :to="`/e/${session.id}/sop`" class="btn btn--secondary"><Icon name="branch" /> Workflow</RouterLink>
        <RouterLink :to="`/e/${session.id}/audit`" class="btn btn--secondary"><Icon name="history" /> Audit</RouterLink>
        <RouterLink :to="`/e/${session.id}`" class="btn btn--primary"><Icon name="edit" /> Open Editor</RouterLink>
      </div>
    </div>

    <div class="sd-grid">
      <!-- Left: session meta -->
      <div class="sd-meta">
        <div class="sd-meta__code">{{ session.code || session.id }}</div>
        <h2 class="sd-meta__title">{{ session.title }}</h2>
        <p class="sd-meta__sub">INTERIM: {{ session.title }}</p>
        <div class="sd-meta__tags">
          <span class="chip chip--ghost" :style="{ textTransform: 'uppercase', letterSpacing: '.06em', fontSize: '10px' }">CE Broker 20-1341518</span>
          <span class="chip chip--blue" :style="{ fontSize: '10px' }">AEMV</span>
          <span class="chip chip--blue" :style="{ fontSize: '10px' }">Behave/Welfare</span>
          <span class="chip chip--blue" :style="{ fontSize: '10px' }">Sm Mam Exotic</span>
        </div>

        <div class="sd-meta__downloads">
          <div class="sd-meta__downloads-head">Downloads</div>
          <button
            v-for="d in downloads"
            :key="d.ext"
            class="sd-meta__download"
            :data-test-id="`sd-download-${d.ext.slice(1)}`"
            :title="d.desc"
            @click="downloadFile(d.ext)"
          >
            <Icon name="download" :size="12" />
            <span class="sd-meta__download-kind">{{ d.kind }}</span>
            <code class="sd-meta__download-ext">{{ d.ext }}</code>
          </button>
        </div>
      </div>

      <!-- Center: KPIs + AI mode -->
      <div class="sd-center">
        <div class="sd-kpis">
          <div class="kpi"><div class="kpi__label">Segments</div><div class="kpi__value">{{ totalSegs }}</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">transcript blocks</div></div>
          <div class="kpi">
            <div class="kpi__label">Avg Confidence</div>
            <div class="kpi__value" :style="{ color: session.avgConf < 75 ? 'var(--color-amber)' : 'var(--color-navy)' }">{{ session.avgConf || 0 }}%</div>
            <div class="kpi__delta" :style="{ color: 'var(--fg2)' }">across all segments</div>
          </div>
          <div class="kpi"><div class="kpi__label">Words</div><div class="kpi__value">{{ (session.words || 0).toLocaleString() }}</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">total spoken</div></div>
          <div class="kpi"><div class="kpi__label">Coverage</div><div class="kpi__value">{{ session.coverage || '—' }}</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">slides assigned</div></div>
          <div class="kpi"><div class="kpi__label">Duration</div><div class="kpi__value">{{ session.duration }}</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">total runtime</div></div>
        </div>

        <div class="sd-row-2">
          <div class="card">
            <div class="card__header"><h3>Alignment</h3></div>
            <div class="card__body" :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }">
              <div>
                <div :style="{ fontSize: '36px', fontWeight: 800, color: 'var(--color-green)', lineHeight: 1 }">{{ session.alignment || 100 }}%</div>
                <div :style="{ fontSize: '11px', color: 'var(--fg2)', marginTop: '4px', textTransform: 'uppercase', letterSpacing: '.08em', fontWeight: 700 }">Auto-aligned</div>
              </div>
              <div>
                <div :style="{ fontSize: '36px', fontWeight: 800, color: 'var(--fg1)', lineHeight: 1 }">{{ totalSegs }}</div>
                <div :style="{ fontSize: '11px', color: 'var(--fg2)', marginTop: '4px', textTransform: 'uppercase', letterSpacing: '.08em', fontWeight: 700 }">Sections</div>
              </div>
            </div>
          </div>
          <div class="card sd-aimode">
            <div class="card__header"><h3>AI Mode — Gemini cleaned filler</h3></div>
            <div class="card__body">
              <div :style="{ display: 'flex', gap: '6px', flexWrap: 'wrap' }">
                <span class="chip chip--blue" :style="{ fontSize: '11px' }">um/uh/er/ah removed</span>
                <span class="chip chip--blue" :style="{ fontSize: '11px' }">Verbatim otherwise</span>
              </div>
              <p :style="{ fontSize: '12px', color: 'var(--fg2)', marginTop: '10px', lineHeight: 1.5 }">
                Three-tier normalization: <strong>raw</strong> → <strong>verbatim-minus-fillers</strong> (default export) → <strong>key points</strong> (optional).
              </p>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card__header">
            <h3 :style="{ color: 'var(--color-amber)' }"><Icon name="alert" :size="12" /> Session files — attention</h3>
            <span class="chip chip--amber" :style="{ fontSize: '10px' }">1 missing</span>
          </div>
          <div class="card__body" :style="{ padding: 0 }">
            <div v-for="f in sessionFiles" :key="f.name" class="sd-file">
              <div class="sd-file__icon"><Icon :name="f.icon" :size="16" /></div>
              <div>
                <div :style="{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }">
                  <strong :style="{ fontSize: '13px', color: 'var(--fg1)' }">{{ f.name }}</strong>
                  <span v-if="f.present" class="chip chip--green" :style="{ fontSize: '9px' }">PRESENT</span>
                  <span v-else class="chip chip--amber" :style="{ fontSize: '9px' }">MISSING</span>
                </div>
                <div :style="{ fontSize: '12px', color: 'var(--fg2)' }">{{ f.desc }}</div>
              </div>
              <button
                :class="['btn', 'btn--sm', f.present ? 'btn--secondary' : 'btn--primary']"
                :data-test-id="`sd-file-${f.name.replace(/\s/g, '_')}`"
                @click="fileAction(f)"
              >{{ f.present ? 'Update' : 'Add' }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: stage assignments + publishing -->
      <div class="sd-right">
        <div class="card">
          <div class="card__header">
            <h3>Stage Assignments</h3>
            <select class="btn btn--secondary btn--sm" :style="{ paddingRight: '24px', fontSize: '11px' }">
              <option>Type: default</option>
              <option>Type: lecture</option>
              <option>Type: rounds</option>
            </select>
          </div>
          <div class="card__body" :style="{ padding: 0 }">
            <template v-for="a in stageAssignments" :key="a.stage">
              <div v-if="stages.find(x => x.id === a.stage)" class="sd-stage-row">
                <div>
                  <div class="sd-stage-row__name">{{ stages.find(x => x.id === a.stage)?.name }}</div>
                  <div :class="['sd-stage-row__who', { 'is-faded': a.faded }]">
                    <span v-if="a.group" :style="{ fontSize: '10px', color: 'var(--fg2)', marginRight: '4px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase' }">Group:</span>
                    {{ a.who }}
                  </div>
                </div>
                <button
                  class="btn btn--ghost btn--icon btn--sm"
                  :data-test-id="`sd-reassign-${a.stage}`"
                  title="Reassign"
                  @click="reassignStage(stages.find(x => x.id === a.stage)?.name ?? '')"
                ><Icon name="edit" /></button>
              </div>
            </template>
          </div>
        </div>

        <div class="card">
          <div class="card__header"><h3>Publishing Links</h3></div>
          <div class="card__body" :style="{ display: 'flex', gap: '6px', flexWrap: 'wrap' }">
            <button
              v-for="p in publishingLinks"
              :key="p"
              class="chip"
              :data-test-id="`sd-pub-${p.replace(/\s/g, '_')}`"
              :style="{ cursor: 'pointer', background: 'var(--surface-bg)', borderColor: 'var(--border-subtle)', padding: '5px 12px' }"
              @click="pubLink(p)"
            >{{ p }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Timeline bar -->
    <div class="sd-timeline-card">
      <div class="sd-timeline-card__head">
        <span :style="{ fontSize: '10px', fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--fg2)' }">
          Timeline · {{ session.duration }} · segments by slide color
        </span>
      </div>
      <div class="sd-timeline">
        <template v-for="sl in slides" :key="sl.id">
          <div
            v-if="(segmentsBySlide.get(sl.id) || []).length > 0"
            class="sd-timeline__seg"
            :style="{
              left: `${((segmentsBySlide.get(sl.id)![0]!.start) / TOTAL_DURATION) * 100}%`,
              width: `${Math.max(0.5, ((segmentsBySlide.get(sl.id)![segmentsBySlide.get(sl.id)!.length - 1]!.end - segmentsBySlide.get(sl.id)![0]!.start) / TOTAL_DURATION) * 100)}%`,
              background: slideAccent(sl.id),
            }"
            :title="`${sl.title} · ${segmentsBySlide.get(sl.id)?.length} segs`"
          />
        </template>
      </div>
      <div class="sd-timeline__axis">
        <span>0:00</span>
        <span>{{ session.duration }}</span>
      </div>
    </div>

    <!-- Segment-level widgets row -->
    <div class="sd-widgets">
      <div class="card">
        <div class="card__header">
          <h3>Segment Confidence</h3>
          <span class="chip chip--ghost" :style="{ fontSize: '10px' }">1–{{ segConfList.length }}</span>
        </div>
        <div class="card__body" :style="{ padding: 0 }">
          <div v-for="s in segConfList" :key="s.n" class="sd-confrow">
            <span :style="{ width: '22px', fontSize: '11px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)' }">{{ s.n }}</span>
            <span :style="{ flex: 1, fontSize: '12px', color: 'var(--fg1)' }">{{ s.conf }}%</span>
            <Icon name="check" :size="11" />
            <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: s.slideColor }" />
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card__header">
          <h3>Slide Assignment</h3>
          <span class="chip chip--ghost" :style="{ fontSize: '10px' }">{{ slides.length }} slides</span>
        </div>
        <div class="card__body" :style="{ padding: 0 }">
          <div v-for="sl in slides.slice(0, 16)" :key="sl.id" class="sd-slideassign">
            <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: slideAccent(sl.id), flexShrink: 0 }" />
            <span :style="{ width: '24px', fontSize: '11px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)', fontWeight: 700 }">{{ String(sl.n).padStart(2, '0') }}</span>
            <span :style="{ flex: 1, fontSize: '12px', color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }">
              {{ sl.title.replace(/^Title — /, '').replace(/^Case Study \d+ — /, '') }}
            </span>
            <span :style="{ fontSize: '10.5px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)' }">{{ segmentsBySlide.get(sl.id)?.length || 0 }} segs</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card__header">
          <h3>Review Queue</h3>
          <span class="chip chip--amber" :style="{ fontSize: '10px' }">{{ reviewQueue.length }} pending</span>
        </div>
        <div class="card__body" :style="{ padding: 0, maxHeight: '380px', overflowY: 'auto' }">
          <div v-if="reviewQueue.length === 0" :style="{ padding: '18px', fontSize: '12px', color: 'var(--fg2)', textAlign: 'center' }">
            No segments flagged for review.
          </div>
          <div v-for="r in reviewQueue" :key="r.id" class="sd-reviewrow">
            <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }">
              <span :style="{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-amber)', fontWeight: 700 }">{{ r.id }} · 0% confidence</span>
              <span :style="{ fontSize: '10px', color: 'var(--fg2)', fontStyle: 'italic' }">{{ r.assignee }}</span>
            </div>
            <div :style="{ fontSize: '12px', color: 'var(--fg1)', lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }">
              {{ r.preview }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>
