/**
 * Audit fixtures — DISCREPANCIES + CORRECTIONS from data.jsx lines 252-277.
 */
export interface Discrepancy {
  id: string;
  seg: string;
  kind: 'drift' | 'punctuation' | 'filler' | 'low_confidence';
  base: string;
  stt: string;
  meaningful: boolean;
  status: 'open' | 'resolved';
}

export const DISCREPANCIES: readonly Discrepancy[] = Object.freeze([
  { id: 'd1', seg: 'seg_005', kind: 'drift',         base: 'fifteen years',                                                stt: 'fifty years',                  meaningful: true,  status: 'open' },
  { id: 'd2', seg: 'seg_008', kind: 'punctuation',   base: 'two thousand nineteen through two thousand twenty four',       stt: '2019 through 2024',            meaningful: false, status: 'open' },
  { id: 'd3', seg: 'seg_010', kind: 'drift',         base: 'with string foreign bodies',                                   stt: 'with strings, foreign bodies', meaningful: true,  status: 'open' },
  { id: 'd4', seg: 'seg_025', kind: 'filler',        base: '(removed: um)',                                                stt: 'um, methadone',                meaningful: false, status: 'resolved' },
  { id: 'd5', seg: 'seg_033', kind: 'low_confidence',base: 'polydioxanone',                                                stt: 'poly-dioxa-known',             meaningful: true,  status: 'resolved' },
  { id: 'd6', seg: 'seg_038', kind: 'drift',         base: 'Cushing or Lembert',                                           stt: 'cushing or lambert',           meaningful: true,  status: 'open' },
  { id: 'd7', seg: 'seg_041', kind: 'drift',         base: "four C's",                                                     stt: 'four sees',                    meaningful: true,  status: 'open' },
  { id: 'd8', seg: 'seg_045', kind: 'filler',        base: '(removed: you know)',                                          stt: 'you know',                     meaningful: false, status: 'resolved' },
]);

export interface Correction {
  id: string;
  t: string;
  seg: string;
  type: 'text_edit' | 'annotation_add' | 'speaker_reassignment' | 'mark_reviewed' | 'chat_insert' | 'slide_reassignment';
  actor: string;
  prior: string | null;
  next: string | null;
  note: string | null;
}

export const CORRECTIONS: readonly Correction[] = Object.freeze([
  { id: 'cor_001', t: '2026-05-14T09:14:22Z', seg: 'seg_005', type: 'text_edit',           actor: 'K. Schultz', prior: 'fifty years',      next: 'fifteen years',   note: 'Drift correction; cross-checked CV.' },
  { id: 'cor_002', t: '2026-05-14T09:18:01Z', seg: 'seg_010', type: 'annotation_add',      actor: 'K. Schultz', prior: null,               next: 'low_confidence',  note: 'Marked low-confidence span.' },
  { id: 'cor_003', t: '2026-05-14T09:22:44Z', seg: 'seg_018', type: 'speaker_reassignment', actor: 'R. Okafor', prior: 'presenter',        next: 'cohost',          note: 'Re-attributed to Dr. Okafor.' },
  { id: 'cor_004', t: '2026-05-14T09:24:08Z', seg: 'seg_033', type: 'text_edit',           actor: 'K. Schultz', prior: 'poly-dioxa-known', next: 'polydioxanone',   note: 'Drug name normalized.' },
  { id: 'cor_005', t: '2026-05-14T09:31:12Z', seg: 'seg_041', type: 'mark_reviewed',       actor: 'M. Mendez',  prior: null,               next: null,              note: null },
  { id: 'cor_006', t: '2026-05-14T09:35:50Z', seg: 'seg_047', type: 'annotation_add',      actor: 'K. Schultz', prior: null,               next: 'uncertain',       note: "Marked 'fifty percent' as uncertain (audio dropout)." },
  { id: 'cor_007', t: '2026-05-14T09:42:17Z', seg: 'seg_012', type: 'chat_insert',         actor: 'K. Schultz', prior: null,               next: 'anchor: seg_012', note: 'Anchored audience question to plication slide.' },
  { id: 'cor_008', t: '2026-05-14T09:48:33Z', seg: 'seg_022', type: 'slide_reassignment',  actor: 'M. Mendez',  prior: 's07',              next: 's08',             note: 'Ultrasound discussion belongs to slide 8.' },
  { id: 'cor_009', t: '2026-05-14T10:02:01Z', seg: 'seg_048', type: 'text_edit',           actor: 'K. Schultz', prior: 'pack warming',     next: 'pack-warming',    note: 'Hyphenation pass.' },
  { id: 'cor_010', t: '2026-05-14T10:05:48Z', seg: 'seg_055', type: 'mark_reviewed',       actor: 'M. Mendez',  prior: null,               next: null,              note: null },
  { id: 'cor_011', t: '2026-05-14T10:11:09Z', seg: 'seg_059', type: 'annotation_add',      actor: 'K. Schultz', prior: null,               next: 'drift',           note: "Marked 'looping through' span." },
  { id: 'cor_012', t: '2026-05-14T10:18:36Z', seg: 'seg_063', type: 'mark_reviewed',       actor: 'M. Mendez',  prior: null,               next: null,              note: null },
]);
