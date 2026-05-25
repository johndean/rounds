/**
 * Settings fixture data — surviving constants only.
 *
 * Per Phase 6 of the 2026-05-23 Settings BUILD plan, the people/groups
 * fixtures (TEAM_PEOPLE / TEAM_GROUPS) and the PROMPT_TEMPLATES fixture
 * were retired in favor of live API calls:
 *   - settingsApi.people()  + settingsApi.groups()  (Phase 1, SectionTypes)
 *   - settingsApi.templatesList()                   (Phase 4, SectionPromptTemplates)
 *
 * What remains is genuinely static config — session-type fallback list,
 * model dropdown options, SOP stage keys — none of which has a backend.
 */

export const SESSION_TYPES: readonly string[] = Object.freeze([
  'default', 'AAFV', 'ABVP', 'AEMV', 'ARAV', 'Cytology Cafe', 'Euro', 'FelineVMA',
  'IVAPM', 'IVFSA', 'IVPA', 'NAVAS', 'Therio', 'Tuesday Topic', 'VECCS',
  'VVI Cage-Side', 'VVI Cage-Side Radiology Rounds',
]);

export interface AiModelOption { v: string; label: string }
export const AI_MODELS: readonly AiModelOption[] = Object.freeze([
  { v: 'gemini-2.5-pro',          label: 'Gemini 2.5 Pro (recommended)' },
  { v: 'gemini-2.5-pro-preview',  label: 'Gemini 2.5 Pro Preview (June)' },
  { v: 'gemini-2.5-flash',        label: 'Gemini 2.5 Flash' },
  { v: 'gemini-2.5-flash-lite',   label: 'Gemini 2.5 Flash Lite (default)' },
  { v: 'gemini-2.5-flash-prev',   label: 'Gemini 2.5 Flash Preview (Apr)' },
  { v: 'gemini-2.0-flash',        label: 'Gemini 2.0 Flash' },
  { v: 'gemini-2.0-flash-lite',   label: 'Gemini 2.0 Flash Lite' },
  { v: 'gemini-1.5-pro',          label: 'Gemini 1.5 Pro' },
  { v: 'gemini-1.5-flash',        label: 'Gemini 1.5 Flash' },
]);

export interface SopStageKey { id: string; label: string }
export const SOP_STAGE_KEYS: readonly SopStageKey[] = Object.freeze([
  { id: 'prep',       label: 'Prep (optional)' },
  { id: 'copy_draft', label: 'Copy Edit — Draft' },
  { id: 'medical',    label: 'Medical Review' },
  { id: 'copy_final', label: 'Copy Edit — Final' },
  { id: 'cms',        label: 'CMS Transcript Published' },
  { id: 'captions',   label: 'Captions on Video' },
  { id: 'qa',         label: 'QA' },
  { id: 'complete',   label: 'Complete (auto-advances)' },
]);
