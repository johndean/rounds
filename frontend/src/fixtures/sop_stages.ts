/**
 * SOP_STAGES — 8-stage workflow definition.
 * Mirrors docs/port-source/data.jsx::SOP_STAGES verbatim (names + order + checks).
 */
export interface SopStage {
  id: string;
  name: string;
  order: number;
  checks: string[];
}

export const SOP_STAGES: readonly SopStage[] = Object.freeze([
  { id: 'prep',       name: 'Prep',                 order: 1,
    checks: ['Audio asset uploaded', 'Slides extracted from PPTX', 'Speaker roster confirmed', 'Ingest pipeline complete'] },
  { id: 'copy_draft', name: 'Copy edit (draft)',    order: 2,
    checks: ['Verbatim-minus-fillers pass complete', 'All needs_review flags first-pass cleared', 'Spelling/punctuation pass', 'Discrepancies triaged'] },
  { id: 'medical',    name: 'Medical review',       order: 3,
    checks: ['Drug names verified against VIN drug index', 'Dosages cross-checked', 'Species/breed terminology validated', 'Reviewer attestation'] },
  { id: 'copy_final', name: 'Copy edit (final)',    order: 4,
    checks: ['Medical review notes incorporated', 'Discrepancies under threshold (< 0.5%)', 'Speaker labels finalized', 'Final readthrough'] },
  { id: 'cms',        name: 'CMS published',        order: 5,
    checks: ['Metadata complete (title, presenter, taxonomy)', 'Key-points layer authored', 'Library taxonomy assigned', 'CE hours computed and attested'] },
  { id: 'captions',   name: 'Captions on video',    order: 6,
    checks: ['SRT generated from finalized timing', 'Wistia upload complete', 'Caption sync verified at 3 sample points', 'Player embed tested'] },
  { id: 'qa',         name: 'QA',                   order: 7,
    checks: ['End-to-end playback (3 spot checks)', 'Mobile rendering verified', 'Search indexing confirmed', 'GCS G1–G14 checks pass'] },
  { id: 'complete',   name: 'Complete',             order: 8,
    checks: ['Live in VIN library', 'Notification to presenter sent', 'Audit ledger archived'] },
]);

export const SOP_STAGE_BY_ID: ReadonlyMap<string, SopStage> = new Map(SOP_STAGES.map(s => [s.id, s]));
