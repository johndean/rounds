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
import AddFileModal from '@/components/session/AddFileModal.vue';
import SessionTextEdit from '@/components/session/SessionTextEdit.vue';
import { SOP_STAGES } from '@/fixtures/sop_stages';
import {
  sessions as sessionsApi,
  segments as segmentsApi,
  settingsApi,
  type SessionSummary,
  type SegmentRow,
  type SessionStageAssigneeRow,
  type SettingsType,
  type SettingsPerson,
  type SettingsGroup,
} from '@/services/api';
import { http } from '@/services/http';
import { slideAccent } from '@/fixtures/transcript';
import { toast } from '@/composables/useToast';
import { confirm } from '@/composables/useConfirm';
import { ApiError } from '@/services/http';

const props = defineProps<{ id: string }>();

interface SourceRow { id: string; role: string; filename: string; gcs_uri: string; content_type: string | null; size_bytes: number | null; duration_sec: number | null; }
interface SlideRow { id: string; slide_index: number; title: string | null; image_uri: string | null; start_ms: number | null; end_ms: number | null; }

const session = ref<SessionSummary | null>(null);

// Title cascade: prefer the extras2-manifest title_long, then title_short,
// then fall back to the auto-generated upload title. Mirrors MIC's
// SessionsListView.vue:433 cascade so the ugly upload code never wins
// when the manifest provided real metadata.
const displayTitle = computed<string>(() =>
  (session.value?.title_long
    || session.value?.title_short
    || session.value?.title
    || ''
  ).trim(),
);

function onTitleSaved(field: 'title' | 'title_long' | 'title_short', next: string): void {
  if (!session.value) return;
  session.value = { ...session.value, [field]: next };
}
function onCodeSaved(next: string): void {
  if (!session.value) return;
  session.value = { ...session.value, code: next };
}
const sources = ref<SourceRow[]>([]);
const slides   = ref<SlideRow[]>([]);
const segments = ref<SegmentRow[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const stages = SOP_STAGES;

// ─── Stage assignment state (Unit 6 — real DB-backed, replaces fixture) ──
const stageAssignments = ref<SessionStageAssigneeRow[]>([]);
const sessionTypes     = ref<SettingsType[]>([]);
const teamPeople       = ref<SettingsPerson[]>([]);
const teamGroups       = ref<SettingsGroup[]>([]);

// Picker state: which stage is currently expanded for inline reassign.
const reassignStageOpen = ref<string | null>(null);
const reassignSaving    = ref(false);

// "Type changed — apply defaults?" banner state. Set when the operator
// changes the Type via the dropdown; cleared once they Apply or Dismiss.
const pendingTypeId = ref<string | null>(null);
const applyingType  = ref(false);

async function load(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [s, src, sl, sg, sa, tps, pp, gg] = await Promise.all([
      sessionsApi.get(props.id).catch(() => null),
      http<SourceRow[]>(`/v1/sessions/${encodeURIComponent(props.id)}/sources`).catch(() => []),
      http<SlideRow[]>(`/v1/sessions/${encodeURIComponent(props.id)}/slides`).catch(() => []),
      segmentsApi.list(props.id).catch(() => []),
      sessionsApi.stageAssignees(props.id).catch(() => [] as SessionStageAssigneeRow[]),
      settingsApi.types().catch(() => [] as SettingsType[]),
      settingsApi.people().catch(() => [] as SettingsPerson[]),
      settingsApi.groups().catch(() => [] as SettingsGroup[]),
    ]);
    session.value = s;
    sources.value = src;
    slides.value = sl;
    segments.value = sg;
    stageAssignments.value = sa;
    sessionTypes.value = tps;
    teamPeople.value = pp.filter((p) => p.is_active !== false);
    teamGroups.value = gg;
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load';
  } finally {
    loading.value = false;
  }
}
onMounted(load);

// Row lookup by stage id — fixture renders one row per SOP_STAGES entry
// and pulls the per-stage assignee out of stageAssignments by stage key.
function assigneeFor(stageId: string): SessionStageAssigneeRow | undefined {
  return stageAssignments.value.find((a) => a.stage === stageId);
}

async function onTypePickerChange(e: Event): Promise<void> {
  const newTypeId = (e.target as HTMLSelectElement).value;
  if (!newTypeId || !session.value) return;
  if (newTypeId === session.value.session_type_id) {
    pendingTypeId.value = null;
    return;
  }
  // Persist the FK immediately; the banner asks before overwriting per-stage assignees.
  try {
    const updated = await sessionsApi.update(props.id, { session_type_id: newTypeId });
    session.value = { ...session.value, session_type_id: updated.session_type_id };
    pendingTypeId.value = newTypeId;
  } catch (err) {
    toast.push(errMsg(err), { tone: 'error' });
  }
}

async function applyTypeDefaults(): Promise<void> {
  if (!pendingTypeId.value || applyingType.value) return;
  const ok = await confirm.open({
    title: 'Apply Type defaults?',
    body: 'This overwrites every stage assignee for this session with the chosen Type\'s matrix. Manual overrides will be replaced.',
    confirmLabel: 'Apply',
    danger: true,
  });
  if (!ok) return;
  applyingType.value = true;
  try {
    await sessionsApi.applyTypeDefaults(props.id, pendingTypeId.value);
    stageAssignments.value = await sessionsApi.stageAssignees(props.id);
    pendingTypeId.value = null;
    toast.push('Stage assignees updated from Type defaults', { tone: 'success' });
  } catch (err) {
    toast.push(errMsg(err), { tone: 'error' });
  } finally {
    applyingType.value = false;
  }
}

function dismissTypeBanner(): void {
  pendingTypeId.value = null;
}

function openReassign(stageId: string): void {
  reassignStageOpen.value = reassignStageOpen.value === stageId ? null : stageId;
}

async function selectAssignee(stageId: string, body: { person_id?: string; group_id?: string }): Promise<void> {
  if (reassignSaving.value) return;
  reassignSaving.value = true;
  try {
    const updated = await sessionsApi.setStageAssignee(props.id, stageId, body);
    stageAssignments.value = stageAssignments.value
      .filter((a) => a.stage !== stageId)
      .concat([updated])
      .sort((a, b) => a.stage.localeCompare(b.stage));
    reassignStageOpen.value = null;
    toast.push(`Reassigned ${stageId}`, { tone: 'success' });
  } catch (err) {
    toast.push(errMsg(err), { tone: 'error' });
  } finally {
    reassignSaving.value = false;
  }
}

async function resetStageToDefault(stageId: string): Promise<void> {
  if (reassignSaving.value) return;
  reassignSaving.value = true;
  try {
    // Empty body triggers backend reset to Type-matrix default for this stage.
    const updated = await sessionsApi.setStageAssignee(props.id, stageId, {});
    stageAssignments.value = stageAssignments.value
      .filter((a) => a.stage !== stageId)
      .concat([updated])
      .sort((a, b) => a.stage.localeCompare(b.stage));
    toast.push(`${stageId} reset to Type default`, { tone: 'success' });
  } catch (err) {
    toast.push(errMsg(err), { tone: 'error' });
  } finally {
    reassignSaving.value = false;
  }
}

function errMsg(e: unknown): string {
  if (e instanceof ApiError) {
    const body = e.body as { detail?: { message?: string } | string } | undefined;
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message;
    if (typeof detail === 'string') return detail;
    return e.message;
  }
  return e instanceof Error ? e.message : 'Request failed';
}

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

// MIC-parity alignment stats (mic/frontend/src/views/EditorView.vue:3218-3220).
// "Aligned" = has a slide assignment; "review" = has any AI flag set
// (matches the reviewQueue filter below). Previously these were hard-coded
// to `100% aligned` + `0 to review`, which lied about session quality
// whenever the aligner silently failed and left segments.slide_id NULL.
const alignedSegs = computed(() => segments.value.filter(s => s.slide_id != null).length);
const reviewSegs  = computed(() => segments.value.filter(s => s.flags && s.flags.length > 0).length);
const alignedPct  = computed(() => totalSegs.value > 0 ? Math.round((alignedSegs.value / totalSegs.value) * 100) : 0);
const alignedChipClass = computed(() => {
  if (totalSegs.value === 0) return 'chip chip--ghost';
  if (alignedPct.value >= 100) return 'chip chip--green';
  if (alignedPct.value >= 80)  return 'chip chip--amber';
  return 'chip chip--red';
});

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

// Phase 2 audit remediation: downloadFile + reassignStage previously
// info-toasted but did nothing. Demoted to honest warn.
function downloadFile(ext: string): void {
  toast.push(
    `${ext.slice(1).toUpperCase()} export not yet wired — ships with Phase 10 exports endpoint.`,
    { tone: 'warn' },
  );
}
// (Legacy reassignStage handler removed — widget now uses openReassign() /
// selectAssignee() via the inline picker.)

// ─── Session-files modal wiring (MIC AddFileModal port) ──────────────
const modalOpen = ref(false);
const modalType = ref<'slides' | 'chat' | 'manifest' | 'bios'>('slides');

const ROLE_TO_MODAL_TYPE: Record<string, 'slides' | 'chat' | 'manifest' | 'bios'> = {
  slide:    'slides',
  chat:     'chat',
  manifest: 'manifest',
  bios:     'bios',
};

function fileAction(f: { name: string; role: string }): void {
  modalType.value = ROLE_TO_MODAL_TYPE[f.role] || 'slides';
  modalOpen.value = true;
}

function onFileSuccess(payload: { type: string; data: unknown }): void {
  toast.push(`${payload.type} saved`, { tone: 'success' });
  void load();   // refetch sources + slides
}

function pubLink(p: string): void {
  // Phase 2 audit remediation: was success-toast with no backend persistence.
  toast.push(
    `${p} link not persisted — publishing-link CRUD ships with Phase 10.`,
    { tone: 'warn' },
  );
}
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
            <span class="chip chip--ghost">
              <SessionTextEdit
                :value="session.code"
                :session-id="session.id"
                field="code"
                variant="code"
                placeholder="e.g. 052026_NTproBNP"
                @save="onCodeSaved"
              />
            </span>
          </div>
          <h1 class="sd-header__title">
            <SessionTextEdit
              :value="displayTitle"
              :session-id="session.id"
              field="title_long"
              variant="title"
              empty-label="+ Add title"
              placeholder="Session title"
              @save="(v) => onTitleSaved('title_long', v)"
            />
          </h1>
          <p class="sd-header__sub">{{ session.presenter || '—' }}</p>
        </div>
        <div class="sd-header__actions">
          <span :class="['chip', reviewSegs > 0 ? 'chip--amber' : 'chip--green']"><span class="chip__dot" /> {{ reviewSegs }} to review</span>
          <span :class="alignedChipClass"><span class="chip__dot" /> {{ alignedPct }}% aligned</span>
          <RouterLink :to="`/e/${session.id}/sop`" class="btn btn--secondary"><Icon name="branch" /> Workflow</RouterLink>
          <RouterLink :to="`/e/${session.id}/audit`" class="btn btn--secondary"><Icon name="history" /> Audit</RouterLink>
          <RouterLink :to="`/e/${session.id}`" class="btn btn--primary"><Icon name="edit" /> Open Editor</RouterLink>
        </div>
      </div>

      <div class="sd-grid">
        <!-- Left: session meta -->
        <div class="sd-meta">
          <div class="sd-meta__code">
            <SessionTextEdit
              :value="session.code"
              :session-id="session.id"
              field="code"
              variant="code"
              placeholder="e.g. 052026_NTproBNP"
              @save="onCodeSaved"
            />
          </div>
          <h2 class="sd-meta__title">
            <SessionTextEdit
              :value="displayTitle"
              :session-id="session.id"
              field="title_long"
              variant="title"
              empty-label="+ Add title"
              placeholder="Session title"
              @save="(v) => onTitleSaved('title_long', v)"
            />
          </h2>
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
                  <div :style="{ fontSize: '36px', fontWeight: 800, color: totalSegs === 0 ? 'var(--fg2)' : alignedPct >= 100 ? 'var(--color-green)' : alignedPct >= 80 ? 'var(--color-amber)' : 'var(--color-red)', lineHeight: 1 }">{{ totalSegs > 0 ? alignedPct : '—' }}<span v-if="totalSegs > 0">%</span></div>
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
              <select
                class="btn btn--secondary btn--sm"
                :style="{ paddingRight: '24px', fontSize: '11px' }"
                :value="session.session_type_id || ''"
                @change="onTypePickerChange"
              >
                <option value="" disabled>Type: select…</option>
                <option v-for="t in sessionTypes" :key="t.id" :value="t.id">
                  Type: {{ t.code }}{{ t.is_default ? ' (default)' : '' }}
                </option>
              </select>
            </div>
            <div
              v-if="pendingTypeId"
              :style="{
                padding: '10px 14px', background: 'rgba(217,119,6,0.10)',
                borderTop: '1px solid var(--border-subtle)',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex', gap: '10px', alignItems: 'center',
                fontSize: '12px', color: 'var(--fg1)',
              }"
            >
              <Icon name="alert" :size="14" />
              <span :style="{ flex: 1 }">
                Type changed — apply this Type's stage defaults? This overwrites manual overrides.
              </span>
              <button
                class="btn btn--primary btn--sm"
                :disabled="applyingType"
                @click="applyTypeDefaults"
              >{{ applyingType ? 'Applying…' : 'Apply' }}</button>
              <button class="btn btn--ghost btn--sm" @click="dismissTypeBanner">Dismiss</button>
            </div>
            <div class="card__body" :style="{ padding: 0 }">
              <template v-for="st in stages" :key="st.id">
                <div class="sd-stage-row">
                  <div :style="{ flex: 1 }">
                    <div class="sd-stage-row__name">
                      {{ st.name }}
                      <span
                        v-if="assigneeFor(st.id)?.source === 'manual'"
                        :style="{
                          marginLeft: '6px', width: '6px', height: '6px',
                          background: 'var(--color-amber)', borderRadius: '50%',
                          display: 'inline-block',
                        }"
                        title="Manual override (not from Type matrix)"
                      ></span>
                    </div>
                    <div
                      :class="['sd-stage-row__who', { 'is-faded': !assigneeFor(st.id) || assigneeFor(st.id)?.assignee_label === '(unassigned)' }]"
                    >
                      <template v-if="assigneeFor(st.id)?.group_name">
                        <span :style="{ fontSize: '10px', color: 'var(--fg2)', marginRight: '4px', fontWeight: 700, letterSpacing: '.06em', textTransform: 'uppercase' }">Group:</span>
                        {{ assigneeFor(st.id)?.group_name }}
                      </template>
                      <template v-else>
                        {{ assigneeFor(st.id)?.assignee_label || '(unassigned)' }}
                      </template>
                    </div>
                  </div>
                  <div :style="{ display: 'inline-flex', gap: '4px', alignItems: 'center' }">
                    <button
                      v-if="assigneeFor(st.id)?.source === 'manual'"
                      class="btn btn--ghost btn--sm"
                      :style="{ fontSize: '10px' }"
                      :data-test-id="`sd-reset-${st.id}`"
                      title="Reset to Type default"
                      @click="resetStageToDefault(st.id)"
                    >Reset</button>
                    <button
                      class="btn btn--ghost btn--icon btn--sm"
                      :data-test-id="`sd-reassign-${st.id}`"
                      title="Reassign"
                      @click="openReassign(st.id)"
                    ><Icon name="edit" /></button>
                  </div>
                </div>
                <div
                  v-if="reassignStageOpen === st.id"
                  :style="{
                    padding: '10px 14px', background: 'var(--surface-bg)',
                    borderTop: '1px solid var(--border-subtle)',
                    borderBottom: '1px solid var(--border-subtle)',
                  }"
                >
                  <div :style="{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--fg2)', fontWeight: 700, marginBottom: '6px' }">
                    People
                  </div>
                  <div :style="{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '10px' }">
                    <button
                      v-for="p in teamPeople"
                      :key="p.id"
                      class="chip"
                      :style="{ cursor: reassignSaving ? 'progress' : 'pointer', fontSize: '11px' }"
                      :disabled="reassignSaving"
                      @click="selectAssignee(st.id, { person_id: p.id })"
                    >{{ p.name }}</button>
                  </div>
                  <div :style="{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--fg2)', fontWeight: 700, marginBottom: '6px' }">
                    Groups
                  </div>
                  <div :style="{ display: 'flex', flexWrap: 'wrap', gap: '4px' }">
                    <button
                      v-for="g in teamGroups"
                      :key="g.id"
                      class="chip"
                      :style="{ cursor: reassignSaving ? 'progress' : 'pointer', fontSize: '11px' }"
                      :disabled="reassignSaving"
                      @click="selectAssignee(st.id, { group_id: g.id })"
                    >Group: {{ g.name }}</button>
                  </div>
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

    <AddFileModal
      v-if="session"
      :open="modalOpen"
      :session-id="session.id"
      :type="modalType"
      :has-existing="hasFile(modalType === 'slides' ? 'slide' : modalType)"
      @close="modalOpen = false"
      @success="onFileSuccess"
    />
  </main>
</template>
