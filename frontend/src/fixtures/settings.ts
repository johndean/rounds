/**
 * Settings fixture data — verbatim port of docs/port-source/settings-pages.jsx
 * lines 6-57. People, groups, session types, AI models, prompt templates, SOP
 * stage keys. Used across the 12 settings sections.
 */

export interface TeamPerson { name: string; email: string }
export const TEAM_PEOPLE: readonly TeamPerson[] = Object.freeze([
  { name: 'Carla Burris',       email: 'carlab@vin.com' },
  { name: 'Debbie Hembroff',    email: 'hembroff@telus.net' },
  { name: 'Erica Hulse',        email: 'ericah@vin.com' },
  { name: 'Heather Howell',     email: 'HeatherH@vin.com' },
  { name: 'Janet Stomberg',     email: 'janet.stomberg@vin.com' },
  { name: 'John Dean',          email: 'john@vetvision.org' },
  { name: 'Lacy Sanders',       email: 'lacy.sanders@vin.com' },
  { name: 'Rachalel Carpenter', email: 'rachael@vin.com' },
  { name: 'Ruth Schoonover',    email: 'ruth@vin.com' },
  { name: 'Tina Payton',        email: 'tina.payton@vin.com' },
]);

export interface TeamGroup { name: string; members: string[] }
export const TEAM_GROUPS: readonly TeamGroup[] = Object.freeze([
  { name: 'Content Team',      members: ['Carla Burris', 'Heather Howell', 'Ruth Schoonover'] },
  { name: 'Debbie (and Team)', members: ['Debbie Hembroff'] },
  { name: 'External',          members: ['Carla Burris', 'Heather Howell', 'Ruth Schoonover'] },
  { name: 'Main Contact',      members: ['Carla Burris'] },
  { name: 'V@V',               members: ['Carla Burris'] },
]);

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
  { v: 'gemini-2.5-flash-prev',   label: 'Gemini 2.5 Flash Preview (Apr)' },
  { v: 'gemini-2.0-flash',        label: 'Gemini 2.0 Flash' },
  { v: 'gemini-2.0-flash-lite',   label: 'Gemini 2.0 Flash Lite' },
  { v: 'gemini-1.5-pro',          label: 'Gemini 1.5 Pro' },
  { v: 'gemini-1.5-flash',        label: 'Gemini 1.5 Flash' },
]);

export interface PromptTemplate {
  id: string;
  cat: string;
  icon: string;
  name: string;
  desc: string;
  chips: string[];
}
export const PROMPT_TEMPLATES: readonly PromptTemplate[] = Object.freeze([
  { id: 'lecture',   cat: 'Education',      icon: '🎓',  name: 'Lecture',                  desc: 'Optimized for structured teaching content',     chips: ['strict', 'neutral', 'medium', 'structure', 'key points'] },
  { id: 'training',  cat: 'Education',      icon: '🛠️', name: 'Training / Workshop',      desc: 'Handles Q&A, exercises and interaction patterns', chips: ['moderate', 'preserve', 'medium', 'structure', 'key points'] },
  { id: 'technical', cat: 'Technical',      icon: '⚙️', name: 'Technical Deep Dive',      desc: 'Terminology preservation — minimal rewrite',     chips: ['moderate', 'preserve', 'strict', 'structure', 'key points'] },
  { id: 'podcast',   cat: 'Conversational', icon: '🎙️', name: 'Podcast / Conversation',   desc: 'Light cleanup — conversational flow preserved', chips: ['light', 'conversational', 'low'] },
  { id: 'sales',     cat: 'Business',       icon: '📊',  name: 'Sales / Presentation',     desc: 'Emphasis and persuasion patterns preserved',    chips: ['moderate', 'persuasive', 'medium', 'structure', 'key points'] },
  { id: 'custom',    cat: 'Custom',         icon: '⚡',  name: 'Custom',                   desc: 'Define your own processing rules',              chips: ['moderate', 'neutral', 'medium', 'structure', 'key points'] },
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
