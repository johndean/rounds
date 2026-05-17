/**
 * SESSIONS — fixture list from docs/port-source/data.jsx (lines 238-249).
 * Verbatim shape + values. Backs SessionsView until the backend has rows.
 */
export interface SessionFixture {
  id: string;
  code: string;
  title: string;
  presenter: string;
  duration: string;
  recorded: string;
  stage: string;
  progress: number;
  attendees: number;
  needsReviewCount: number;
  presence: readonly string[];
  status: 'active' | 'processing' | 'complete';
  segs: number;
  words: number;
  avgConf: number;
  alignment: number;
  coverage: string;
}

export const SESSIONS: readonly SessionFixture[] = Object.freeze([
  { id: 'se_001', code: '060524_Mueller',     title: 'Surgical Approach to GI Foreign Body Removal',                presenter: 'Dr. Pamela Mueller',  duration: '1h 04m', recorded: '2026-05-14', stage: 'copy_draft', progress: 38,  attendees: 612,  needsReviewCount: 7,  presence: ['JH','RO','KS'], status: 'active',     segs: 66,  words: 6240,  avgConf: 82, alignment: 100, coverage: '24/24' },
  { id: 'se_002', code: '010726_Pickles',     title: 'Crafting a Neurodivergent Career in Veterinary Practice',     presenter: 'Dr. Kirstie Pickles', duration: '0h 58m', recorded: '2026-05-13', stage: 'medical',    progress: 36,  attendees: 489,  needsReviewCount: 14, presence: ['KP','JH'],       status: 'active',     segs: 73,  words: 6892,  avgConf: 82, alignment: 100, coverage: '26/26' },
  { id: 'se_003', code: '041526_JepsenGrant', title: 'Cage-Side Radiology Rounds: Various Cases',                   presenter: 'Dr. Hiro Tanaka',     duration: '1h 12m', recorded: '2026-05-12', stage: 'copy_final', progress: 62,  attendees: 287,  needsReviewCount: 2,  presence: ['HT'],            status: 'active',     segs: 120, words: 9120,  avgConf: 78, alignment: 95,  coverage: '18/18' },
  { id: 'se_004', code: '042326_Anaphylaxis', title: 'Anaphylaxis in the Emergency Setting',                        presenter: 'Dr. Reggie Okafor',   duration: '0h 47m', recorded: '2026-05-11', stage: 'qa',         progress: 88,  attendees: 1024, needsReviewCount: 0,  presence: ['RO','JH','KS','MM'], status: 'active', segs: 54,  words: 5612,  avgConf: 91, alignment: 100, coverage: '14/14' },
  { id: 'se_005', code: '050726_Cytology',    title: 'Cytology of Cutaneous Round Cell Tumors',                     presenter: 'Dr. Aliyah Khan',     duration: '1h 18m', recorded: '2026-05-09', stage: 'captions',   progress: 72,  attendees: 391,  needsReviewCount: 1,  presence: ['AK','JH'],       status: 'active',     segs: 132, words: 10240, avgConf: 84, alignment: 98,  coverage: '29/29' },
  { id: 'se_006', code: '050726_OLeary',      title: 'Feline Corneal Disease: Cats Are Not Small Dogs!',            presenter: "Dr. Patrick O'Leary", duration: '1h 05m', recorded: '2026-05-08', stage: 'cms',        progress: 80,  attendees: 1208, needsReviewCount: 0,  presence: ['PL'],            status: 'active',     segs: 73,  words: 7104,  avgConf: 88, alignment: 100, coverage: '21/21' },
  { id: 'se_007', code: '050626_GeriPain',    title: 'Pain Management in the Geriatric Cat',                        presenter: 'Dr. Emma Rivera',     duration: '0h 51m', recorded: '2026-05-06', stage: 'prep',       progress: 4,   attendees: 0,    needsReviewCount: 0,  presence: ['MM'],            status: 'processing', segs: 0,   words: 0,     avgConf: 0,  alignment: 0,   coverage: '0/0' },
  { id: 'se_008', code: '050526_ReproImg',    title: 'Reproductive Imaging in the Bitch — Ultrasound Pearls',        presenter: 'Dr. Jamie Forsythe',  duration: '0h 56m', recorded: '2026-05-05', stage: 'complete',   progress: 100, attendees: 736,  needsReviewCount: 0,  presence: [],                status: 'complete',   segs: 88,  words: 7320,  avgConf: 90, alignment: 100, coverage: '19/19' },
  { id: 'se_009', code: '050326_Hypoadr',     title: 'Hypoadrenocorticism — Atypical Presentations',                 presenter: 'Dr. Marcus Yates',    duration: '1h 09m', recorded: '2026-05-03', stage: 'complete',   progress: 100, attendees: 542,  needsReviewCount: 0,  presence: [],                status: 'complete',   segs: 108, words: 8540,  avgConf: 89, alignment: 100, coverage: '23/23' },
  { id: 'se_010', code: '050126_AvianBeak',   title: 'Avian Beak & Nail Trimming — A Hands-On Refresher',           presenter: 'Dr. Sunita Rao',      duration: '0h 39m', recorded: '2026-05-01', stage: 'complete',   progress: 100, attendees: 218,  needsReviewCount: 0,  presence: [],                status: 'complete',   segs: 48,  words: 4180,  avgConf: 87, alignment: 100, coverage: '12/12' },
]);
