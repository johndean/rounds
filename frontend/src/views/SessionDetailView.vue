<script setup lang="ts">
/**
 * Session Detail — /s/:id
 *
 * Same DOM as React session-detail.jsx. Wired to live backend:
 *   GET /v1/sessions/{id}            — session shell
 *   GET /v1/sessions/{id}/sources    — uploaded files
 *   GET /v1/sessions/{id}/slides     — extracted slides (post-ingest)
 *   GET /v1/sessions/{id}/segments   — AI transcript segments (post-ingest)
 *
 * Empty arrays render empty-state copy; layout stays intact so visual
 * parity vs React holds whether the session has been ingested or not.
 */
import { computed, onMounted, ref } from 'vue';
import Icon from '@/components/shared/Icon.vue';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import {
  sessions as sessionsApi,
  segments as segmentsApi,
  type SessionSummary,
  type SegmentRow,
} from '@/services/api';
import { http } from '@/services/http';
import { slideAccent } from '@/fixtures/transcript';
import { toast } from '@/composables/useToast';

const props = defineProps<{ id: string }>();

interface SourceRow { id: string; role: string; filename: string; gcs_uri: string; content_type: string | null; size_bytes: number | null; duration_sec: number | null; }
interface SlideRow { id: string; slide_index: number; title: string | null; image_uri: string | null; start_ms: number | null; end_ms: number | null; }

const session = ref<SessionSummary | null>(null);
const sources = ref<SourceRow[]>([]);
const slides   = ref<SlideRow[]>([]);
const segments = ref<SegmentRow[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const stages = SOP_STAGES;

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [s, src, sl, sg] = await Promise.all([
      sessionsApi.get(props.id).catch(() => null),
      http<SourceRow[]>(`/v1/sessions/${encodeURIComponent(props.id)}/sources`).catch(() => []),
      http<SlideRow[]>(`/v1/sessions/${encodeURIComponent(props.id)}/slides`).catch(() => []),
      segmentsApi.list(props.id).catch(() => []),
    ]);
    session.value = s;
    sources.value = src;
    slides.value = sl;
    segments.value = sg;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const stageAssignments = [
  { stage: 'copy_draft', who: '(unassigned)',                  group: false, faded: true },
  { stage: 'medical',    who: 'V@V · Heather Howell',           group: false, faded: false },
  { stage: 'copy_final', who: 'Main Contact · Ruth Schoonover', group: false, faded: false },
  { stage: 'cms',        who: 'Content Team (default)',         group: true,  faded: false },
  { stage: 'captions',   who: 'Content Team',                   group: false, faded: false },
  { stage: 'qa',         who: 'Content Team (default)',         group: true,  faded: false },
];

const publishingLinks = ['Zoom recording', 'Slides', 'Podbean', 'VINcast', 'Intranet', 'Session page'];
const downloads = [
  { kind: 'Word Document',  ext: '.docx', desc: 'Macro-compatible transcript with slide codes and speaker labels.' },
  { kind: 'Captions',       ext: '.srt',  desc: 'SubRip subtitle file for Wistia or video player.' },
  { kind: 'Plain Text',     ext: '.txt',  desc: 'Simple text for email, forum paste, or quick reference.' },
  { kind: 'Word Macro',     ext: '.zip',  desc: 'One-time install. Developer → Visual Basic → Import.' },
];

const totalSegs = computed(() => session.value?.segment_count ?? segments.value.length);
const totalDurationMs = computed(() => (session.value?.duration_sec ?? 0) * 1000);
const totalWords = computed(() => session.value?.word_count ?? 0);

function hasFile(role: string): boolean {
  return sources.value.some(s => s.role === role);
}

const sessionFiles = computed(() => [
  { name: 'Slides',           role: 'slide',    icon: 'slide',   desc: hasFile('slide')    ? 'Slides extracted — you can replace or append a new deck.' : 'No slides uploaded yet.' },
  { name: 'Chat log',         role: 'chat',     icon: 'message', desc: hasFile('chat')     ? 'Chat present — uploading new chat replaces existing messages.' : 'No chat log uploaded yet.' },
  { name: 'Session manifest', role: 'manifest', icon: 'doc',     desc: hasFile('manifest') ? 'Manifest present — you can use a new one or keep current.' : 'No manifest uploaded yet.' },
  { name: 'Speaker bios',     role: 'bios',     icon: 'user',    desc: hasFile('bios')     ? 'Speaker bios uploaded.' : "Without bios, speaker credentials won't render in the export." },
]);
const missingCount = computed(() => sessionFiles.value.filter(f => !hasFile(f.role)).length);

const segmentsBySlide = computed(() => {
  const m = new Map<string, SegmentRow[]>();
  slides.value.forEach(sl => m.set(sl.id, []));
  segments.value.forEach(s => { if (s.slide_id) (m.get(s.slide_id) || m.set(s.slide_id, []).get(s.slide_id))!.push(s); });
  return m;
});

const reviewQueue = computed(() => segments.value
  .filter(s => s.flags && s.flags.length > 0).slice(0, 10).map((s, i) => ({
    id: `g${95 + i}`,
    seg: s.id,
    conf: typeof s.confidence === 'number' ? Math.round(s.confidence * 100) : 0,
    preview: s.text.slice(0, 80) + (s.text.length > 80 ? '…' : ''),
    assignee: 'unassigned',
  })));

const segConfList = computed(() => segments.value.slice(0, 31).map((s, i) => {
  const pct = typeof s.confidence === 'number' ? Math.round(s.confidence * 100) : 0;
  return { n: i + 1, conf: pct, ok: pct >= 80 ? 'ok' : 'warn', slideColor: slideAccent(s.slide_id ?? null) };
}));

function durationLabel(): string {
  const total = session.value?.duration_sec ?? 0;
  if (!total) return '—';
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  return h > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`;
}

function downloadFile(ext: string): void {
  toast.push(`Download ${ext.slice(1).toUpperCase()} (lands once exports endpoint is wired)`, { tone: 'info' });
}
function reassignStage(name: string): void { toast.push(`Reassign ${name} — picker (mock)`); }
function fileAction(f: { name: string; role: string }): void {
  toast.push(`${hasFile(f.role) ? 'Update' : 'Add'} ${f.name} — file picker pending`);
}
function pubLink(p: string): void { toast.push(`${p} — link saved (mock)`, { tone: 'success' }); }
</script>

<template>
  <main class="page" :data-screen-label="`Session Detail / ${props.id}`">
    <div class="page-eyebrow">
      <RouterLink to="/sessions">Sessions</RouterLink>
      <span class="sep">/</span>
      <code :style="{ fontFamily: 'var(--font-mono)', color: 'var(--fg-link)' }">{{ session?.code || props.id }}</code>
    </div>

    <div v-if="loading" :style="{ padding: '60px', textAlign: 'center', color: 'var(--fg2)' }">Loading session…</div>
    <div v-else-if="error" :style="{ padding: '60px', textAlign: 'center', color: 'var(--color-red)' }">{{ error }}</div>
    <div v-else-if="!session" :style="{ padding: '60px', textAlign: 'center', color: 'var(--fg2)' }">
      Session not found.
      <RouterLink to="/sessions" :style="{ marginLeft: '6px' }">← Back to sessions</RouterLink>
    </div>
    <template v-else>
      <!-- Header strip -->
      <div class="sd-header">
        <div>
          <div :style="{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '6px' }">
            <span :class="['chip', session.status === 'ready' || session.status === 'complete' ? 'chip--green' : 'chip--amber']">
              <Icon name="check" :size="10" /> {{ session.status }}
            </span>
            <span class="chip chip--ghost">{{ session.code }}</span>
          </div>
          <h1 class="sd-header__title">{{ session.title }}</h1>
          <p class="sd-header__sub">{{ session.presenter || '—' }}</p>
        </div>
        <div class="sd-header__actions">
          <span class="chip chip--amber"><span class="chip__dot" /> 0 to review</span>
          <span class="chip chip--green"><span class="chip__dot" /> {{ totalSegs > 0 ? 100 : 0 }}% aligned</span>
          <RouterLink :to="`/e/${session.id}/sop`" class="btn btn--secondary"><Icon name="branch" /> Workflow</RouterLink>
          <RouterLink :to="`/e/${session.id}/audit`" class="btn btn--secondary"><Icon name="history" /> Audit</RouterLink>
          <RouterLink :to="`/e/${session.id}`" class="btn btn--primary"><Icon name="edit" /> Open Editor</RouterLink>
        </div>
      </div>

      <div class="sd-grid">
        <!-- Left: session meta -->
        <div class="sd-meta">
          <div class="sd-meta__code">{{ session.code }}</div>
          <h2 class="sd-meta__title">{{ session.title }}</h2>
          <p class="sd-meta__sub">{{ session.presenter || '—' }}</p>
          <div class="sd-meta__tags">
            <span v-for="t in (session.taxonomy.length ? session.taxonomy : ['untagged'])" :key="t" class="chip chip--blue" :style="{ fontSize: '10px' }">{{ t }}</span>
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
            <div class="kpi"><div class="kpi__label">Avg Confidence</div><div class="kpi__value">—</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">post-ingest</div></div>
            <div class="kpi"><div class="kpi__label">Words</div><div class="kpi__value">{{ totalWords.toLocaleString() }}</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">total spoken</div></div>
            <div class="kpi"><div class="kpi__label">Sources</div><div class="kpi__value">{{ sources.length }}</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">files uploaded</div></div>
            <div class="kpi"><div class="kpi__label">Duration</div><div class="kpi__value">{{ durationLabel() }}</div><div class="kpi__delta" :style="{ color: 'var(--fg2)' }">total runtime</div></div>
          </div>

          <div class="sd-row-2">
            <div class="card">
              <div class="card__header"><h3>Alignment</h3></div>
              <div class="card__body" :style="{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }">
                <div>
                  <div :style="{ fontSize: '36px', fontWeight: 800, color: totalSegs > 0 ? 'var(--color-green)' : 'var(--fg2)', lineHeight: 1 }">{{ totalSegs > 0 ? '100' : '—' }}<span v-if="totalSegs > 0">%</span></div>
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
              <h3 :style="{ color: missingCount > 0 ? 'var(--color-amber)' : 'var(--color-green)' }">
                <Icon name="alert" :size="12" /> Session files — attention
              </h3>
              <span :class="['chip', missingCount > 0 ? 'chip--amber' : 'chip--green']" :style="{ fontSize: '10px' }">
                {{ missingCount > 0 ? `${missingCount} missing` : 'all present' }}
              </span>
            </div>
            <div class="card__body" :style="{ padding: 0 }">
              <div v-for="f in sessionFiles" :key="f.name" class="sd-file">
                <div class="sd-file__icon"><Icon :name="f.icon" :size="16" /></div>
                <div>
                  <div :style="{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }">
                    <strong :style="{ fontSize: '13px', color: 'var(--fg1)' }">{{ f.name }}</strong>
                    <span v-if="hasFile(f.role)" class="chip chip--green" :style="{ fontSize: '9px' }">PRESENT</span>
                    <span v-else class="chip chip--amber" :style="{ fontSize: '9px' }">MISSING</span>
                  </div>
                  <div :style="{ fontSize: '12px', color: 'var(--fg2)' }">{{ f.desc }}</div>
                </div>
                <button
                  :class="['btn', 'btn--sm', hasFile(f.role) ? 'btn--secondary' : 'btn--primary']"
                  :data-test-id="`sd-file-${f.name.replace(/\s/g, '_')}`"
                  @click="fileAction(f)"
                >{{ hasFile(f.role) ? 'Update' : 'Add' }}</button>
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
            Timeline · {{ durationLabel() }} · segments by slide color
          </span>
        </div>
        <div class="sd-timeline">
          <template v-for="sl in slides" :key="sl.id">
            <div
              v-if="(segmentsBySlide.get(sl.id) || []).length > 0 && totalDurationMs > 0"
              class="sd-timeline__seg"
              :style="{
                left: `${((segmentsBySlide.get(sl.id)![0]!.start_ms) / totalDurationMs) * 100}%`,
                width: `${Math.max(0.5, ((segmentsBySlide.get(sl.id)![segmentsBySlide.get(sl.id)!.length - 1]!.end_ms - segmentsBySlide.get(sl.id)![0]!.start_ms) / totalDurationMs) * 100)}%`,
                background: slideAccent(sl.id),
              }"
              :title="`${sl.title} · ${segmentsBySlide.get(sl.id)?.length} segs`"
            />
          </template>
          <div v-if="slides.length === 0" :style="{ padding: '20px', color: 'var(--fg2)', fontSize: '12px', textAlign: 'center' }">
            No slides yet — ingest pending.
          </div>
        </div>
        <div class="sd-timeline__axis">
          <span>0:00</span>
          <span>{{ durationLabel() }}</span>
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
            <div v-if="segConfList.length === 0" :style="{ padding: '18px', fontSize: '12px', color: 'var(--fg2)', textAlign: 'center' }">No segments yet.</div>
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
            <div v-if="slides.length === 0" :style="{ padding: '18px', fontSize: '12px', color: 'var(--fg2)', textAlign: 'center' }">No slides yet.</div>
            <div v-for="sl in slides.slice(0, 16)" :key="sl.id" class="sd-slideassign">
              <span :style="{ width: '8px', height: '8px', borderRadius: '50%', background: slideAccent(sl.id), flexShrink: 0 }" />
              <span :style="{ width: '24px', fontSize: '11px', color: 'var(--fg2)', fontFamily: 'var(--font-mono)', fontWeight: 700 }">{{ String(sl.slide_index + 1).padStart(2, '0') }}</span>
              <span :style="{ flex: 1, fontSize: '12px', color: 'var(--fg1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }">{{ sl.title || '—' }}</span>
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
            <div v-if="reviewQueue.length === 0" :style="{ padding: '18px', fontSize: '12px', color: 'var(--fg2)', textAlign: 'center' }">No segments flagged for review.</div>
            <div v-for="r in reviewQueue" :key="r.id" class="sd-reviewrow">
              <div :style="{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }">
                <span :style="{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-amber)', fontWeight: 700 }">{{ r.id }} · {{ r.conf }}% confidence</span>
                <span :style="{ fontSize: '10px', color: 'var(--fg2)', fontStyle: 'italic' }">{{ r.assignee }}</span>
              </div>
              <div :style="{ fontSize: '12px', color: 'var(--fg1)', lineHeight: 1.4 }">{{ r.preview }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </main>
</template>
