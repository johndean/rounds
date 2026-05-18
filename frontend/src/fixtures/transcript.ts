/**
 * Transcript fixture — SPEAKERS + SLIDES + SEGMENTS + TOTAL_DURATION.
 * Verbatim port of docs/port-source/data.jsx lines 5-160.
 * The fictional "Surgical Approach to GI Foreign Body Removal" CE webinar.
 */

export interface Speaker {
  id: string;
  name: string;
  short: string;
  role: string;
  color: string;
}

export const SPEAKERS: Readonly<Record<'presenter' | 'cohost' | 'moderator', Speaker>> = Object.freeze({
  presenter: { id: 'sp1', name: 'Dr. Pamela Mueller, DVM, DACVS', short: 'Dr. Mueller', role: 'Presenter', color: '#002855' },
  cohost:    { id: 'sp2', name: 'Dr. Reggie Okafor, DVM',        short: 'Dr. Okafor', role: 'Co-host',   color: '#007D61' },
  moderator: { id: 'sp3', name: 'Jenna Hsu, RVT (Moderator)',    short: 'J. Hsu',     role: 'Moderator', color: '#B9975B' },
});

export type SpeakerKey = keyof typeof SPEAKERS;

export interface Slide {
  id: string;
  n: number;
  title: string;
  kind: string;
}

export const SLIDES: readonly Slide[] = Object.freeze([
  { id: 's01', n: 1,  title: 'Title — Surgical Approach to GI Foreign Body Removal', kind: 'title' },
  { id: 's02', n: 2,  title: 'Speaker Bio & Disclosures',                              kind: 'bio' },
  { id: 's03', n: 3,  title: 'Learning Objectives',                                    kind: 'objectives' },
  { id: 's04', n: 4,  title: 'Epidemiology of GI FB in Small Animals',                 kind: 'data' },
  { id: 's05', n: 5,  title: 'Common Foreign Bodies — Linear vs Discrete',             kind: 'comparison' },
  { id: 's06', n: 6,  title: 'Clinical Presentation',                                  kind: 'list' },
  { id: 's07', n: 7,  title: 'Diagnostic Imaging — Radiograph Patterns',               kind: 'image' },
  { id: 's08', n: 8,  title: 'Ultrasound Findings',                                    kind: 'image' },
  { id: 's09', n: 9,  title: 'Preoperative Stabilization',                             kind: 'protocol' },
  { id: 's10', n: 10, title: 'Anesthetic Plan & Monitoring',                           kind: 'protocol' },
  { id: 's11', n: 11, title: 'Surgical Site Preparation',                              kind: 'list' },
  { id: 's12', n: 12, title: 'Enterotomy — Technique & Closure',                       kind: 'technique' },
  { id: 's13', n: 13, title: 'Gastrotomy — Indications & Approach',                    kind: 'technique' },
  { id: 's14', n: 14, title: 'Resection & Anastomosis Decision Tree',                  kind: 'flow' },
  { id: 's15', n: 15, title: 'Closure Patterns — Comparison Study',                    kind: 'data' },
  { id: 's16', n: 16, title: 'Postoperative Care',                                     kind: 'list' },
  { id: 's17', n: 17, title: 'Complications — Dehiscence & Septic Peritonitis',        kind: 'list' },
  { id: 's18', n: 18, title: 'Case Study 01 — Sock Obstruction in a 4yo Lab',          kind: 'case' },
  { id: 's19', n: 19, title: 'Case Study 02 — Linear FB in a DSH',                     kind: 'case' },
  { id: 's20', n: 20, title: 'Owner Communication & Prognosis',                        kind: 'list' },
  { id: 's21', n: 21, title: 'Pearls & Pitfalls',                                      kind: 'list' },
  { id: 's22', n: 22, title: 'Q&A',                                                    kind: 'qa' },
  { id: 's23', n: 23, title: 'References',                                             kind: 'refs' },
  { id: 's24', n: 24, title: 'Thank You',                                              kind: 'title' },
]);

export interface AiFlag { w: number; kind: 'drift' | 'uncertain' | 'low_confidence' }
type RawRow = [slideId: string, speakerKey: SpeakerKey, text: string, flags: AiFlag[], needsReview: boolean];

const RAW_SEGMENTS: ReadonlyArray<RawRow> = [
  ['s01', 'moderator', "Good morning everyone and welcome to today's continuing education session on the surgical approach to gastrointestinal foreign body removal in small animals.", [], false],
  ['s01', 'moderator', "I'm Jenna Hsu and I'll be moderating today's session. Before we begin, a reminder that this webinar is being recorded for the VIN library.", [], false],
  ['s01', 'moderator', "Our presenter today is Dr. Pamela Mueller, a board-certified surgeon at the University of Wisconsin School of Veterinary Medicine.", [], false],
  ['s02', 'presenter', "Thank you Jenna. It's a pleasure to be here. Before we dive in, a quick disclosure — I have no relevant financial relationships with any commercial entities.", [], false],
  ['s02', 'presenter', "I've been practicing soft tissue surgery for fifteen years and gastrointestinal foreign body removal remains one of the most common procedures we perform.", [{ w: 18, kind: 'uncertain' }], false],
  ['s03', 'presenter', "By the end of this hour you should be able to recognize the four classic radiographic patterns of GI obstruction, decide between enterotomy and resection-anastomosis, and counsel owners on realistic prognosis.", [], true],
  ['s03', 'presenter', "We'll cover the decision-making framework I use intraoperatively and walk through two case studies from our teaching hospital.", [], false],
  ['s04', 'presenter', "Looking at our institutional data from 2019 through 2024 we saw roughly twelve hundred GI foreign body cases across companion animal species.", [{ w: 11, kind: 'low_confidence' }], false],
  ['s04', 'presenter', "Dogs accounted for about seventy-eight percent of cases, cats for nineteen percent, and the remaining three percent were small mammals or exotics.", [], false],
  ['s04', 'presenter', "The peak incidence in dogs is between one and four years of age. In cats it's bimodal — young cats with string foreign bodies and senior cats with linear obstructions from thread.", [{ w: 24, kind: 'drift' }, { w: 25, kind: 'drift' }], true],
  ['s05', 'presenter', "Foreign bodies fall broadly into two categories — discrete and linear. Discrete bodies are usually toys, bones, corn cobs, balls, rocks.", [], false],
  ['s05', 'presenter', "Linear foreign bodies are far more dangerous because of the plication mechanism they cause. String, thread, fishing line, dental floss, and clothing all qualify.", [], false],
  ['s05', 'presenter', "If you remember nothing else from today, remember this — never pull on a linear foreign body until you have confirmed it is not anchored proximally.", [], true],
  ['s06', 'presenter', "Presenting signs depend on the level and completeness of obstruction. Proximal complete obstructions present with violent unproductive vomiting within hours.", [], false],
  ['s06', 'presenter', "Distal or partial obstructions can be more insidious — intermittent vomiting, anorexia, and a slow decline over three to seven days.", [], false],
  ['s06', 'presenter', "On physical exam you may palpate a discrete mass, detect bunched intestinal loops, or find a string anchored under the tongue in cats.", [{ w: 16, kind: 'uncertain' }], false],
  ['s06', 'cohost',    "Pam, can I jump in here? I want to emphasize that the sublingual exam is non-negotiable in any vomiting cat. We miss it routinely in practice.", [], false],
  ['s06', 'presenter', "Absolutely. Every vomiting cat gets a sedated oral exam if you can't get a good look awake. Reggie that's a great point.", [], false],
  ['s07', 'presenter', "On survey radiographs we look for four patterns. Pattern one — discrete radiopaque foreign body, easiest case.", [], false],
  ['s07', 'presenter', "Pattern two — gravel sign distal to the obstruction indicating chronicity. Pattern three — plication and gas pattern suggesting a linear foreign body.", [], false],
  ['s07', 'presenter', "Pattern four — generalized ileus without an obvious cause. This is the trickiest and often requires contrast or ultrasound.", [], true],
  ['s08', 'presenter', "Ultrasound has largely replaced contrast studies in our institution. With a competent sonographer you can identify the obstruction site, assess wall thickness, and evaluate for free fluid.", [{ w: 22, kind: 'uncertain' }], false],
  ['s08', 'presenter', "Free abdominal fluid in this context is a red flag for perforation and converts the case from elective to emergency.", [], false],
  ['s09', 'presenter', "Before you cut, stabilize. A bolus of balanced crystalloid at ten to twenty milliliters per kilogram over fifteen minutes corrects most cases of mild dehydration.", [], false],
  ['s09', 'presenter', "Check electrolytes. Hypokalemia and hypochloremia are common with proximal obstructions and worsen anesthetic risk.", [], true],
  ['s09', 'presenter', "Pre-emptive analgesia matters. I use methadone at point five milligrams per kilogram intramuscularly as part of premedication.", [{ w: 9, kind: 'low_confidence' }], false],
  ['s10', 'presenter', "Our standard anesthetic protocol for GI surgery is methadone-midazolam premed, propofol induction, and isoflurane maintenance with an opioid CRI intraoperatively.", [], false],
  ['s10', 'presenter', "Monitoring should include capnography, doppler or oscillometric blood pressure, ECG, and core temperature. These cases lose heat fast on the open abdomen.", [], false],
  ['s10', 'cohost',    "I'll add — if you don't have a forced-air warming device, get one before you do another abdominal surgery. It's the single biggest equipment upgrade we've made.", [], false],
  ['s11', 'presenter', "Clip generously — xiphoid to pubis, well past the lateral midline on both sides. You will be surprised how often you need to extend the incision cranially or caudally.", [], false],
  ['s11', 'presenter', "Three-stage prep with chlorhexidine scrub, alternating with alcohol, then a final paint. Draping should expose the entire ventral midline.", [], false],
  ['s12', 'presenter', "Enterotomy is the workhorse procedure. Choose an incision site on the antimesenteric border just distal to the foreign body in healthy-appearing tissue.", [], true],
  ['s12', 'presenter', "I use a number eleven blade for the initial stab and extend with Metzenbaum scissors to a length adequate to deliver the foreign body without tearing.", [], false],
  ['s12', 'presenter', "Closure is single-layer simple interrupted appositional with three-zero polydioxanone on a taper needle. Bite five millimeters from the cut edge with five millimeters between bites.", [{ w: 13, kind: 'drift' }], false],
  ['s12', 'presenter', "Some surgeons advocate for a Gambee pattern. The evidence does not show a meaningful difference in dehiscence rates so go with what gives you the most consistent technique.", [{ w: 6, kind: 'uncertain' }], false],
  ['s13', 'presenter', "Gastrotomy is indicated when the foreign body is gastric and cannot be retrieved endoscopically. Make your incision in a hypovascular area between the greater and lesser curvatures.", [], false],
  ['s13', 'presenter', "Two-layer closure for gastrotomy — inverting Cushing or Lembert in the seromuscular layer over a simple continuous mucosal layer.", [], false],
  ['s14', 'presenter', "When do you resect versus repair? Three criteria push me toward resection — non-viability on assessment, perforation, or a closure that would compromise more than fifty percent of the lumen.", [], true],
  ['s14', 'presenter', "Assess viability with the four C's — color, contractility, capillary perfusion, and pulsation in the mesenteric arcade. Pink, contractile, bleeding, and pulsing means leave it.", [{ w: 14, kind: 'uncertain' }], false],
  ['s14', 'presenter', "Dark purple, flaccid, non-bleeding, and absent pulse means resect. Equivocal cases — wait five minutes after pack-warming and reassess.", [], false],
  ['s15', 'presenter', "Our retrospective review of six hundred enterotomies showed no statistically significant difference between simple interrupted appositional and modified Gambee closures.", [{ w: 6, kind: 'low_confidence' }], false],
  ['s15', 'presenter', "Dehiscence rates were two point eight percent and three point one percent respectively, with a p value of zero point six four.", [], false],
  ['s16', 'presenter', "Postoperative care — small frequent meals starting twelve to twenty-four hours after surgery, continued IV fluids until eating reliably, multimodal analgesia for at least seventy-two hours.", [], false],
  ['s16', 'presenter', "I send everyone home on a five-day course of trazodone for sedation. Compliance with activity restriction is the single biggest driver of outcomes in my experience.", [{ w: 11, kind: 'drift' }], true],
  ['s17', 'presenter', "The two complications that will keep you up at night are dehiscence and septic peritonitis. They typically present three to five days postoperatively with sudden decompensation.", [], false],
  ['s17', 'presenter', "Any patient that fails to progress as expected gets re-imaged. Free fluid plus clinical decline equals return to surgery — do not wait for confirmation.", [], false],
  ['s18', 'presenter', "Our first case — Murphy, a four-year-old neutered male Labrador, presented with a twenty-four-hour history of vomiting and one episode of bloody diarrhea overnight.", [], false],
  ['s18', 'presenter', "Radiographs showed a discrete soft tissue opacity in the proximal jejunum with gas dilation orad to the obstruction. Surgery confirmed a child's sock causing complete obstruction.", [{ w: 19, kind: 'uncertain' }], false],
  ['s18', 'presenter', "Single enterotomy on the antimesenteric border, retrieval without resection, simple interrupted appositional closure. Discharged on day two, no complications at the two-week recheck.", [], false],
  ['s19', 'presenter', "Our second case — Mochi, a seven-year-old spayed female domestic shorthair, presented with three days of anorexia and intermittent vomiting.", [], false],
  ['s19', 'presenter', "Sublingual exam revealed thread anchored at the base of the tongue. Radiographs showed classic plication. Ultrasound showed no free fluid so we proceeded to surgery the same day.", [], true],
  ['s19', 'presenter', "At surgery we found the thread anchored sublingually and looping through approximately forty centimeters of jejunum with one focal area of full thickness compromise.", [{ w: 16, kind: 'drift' }, { w: 17, kind: 'drift' }], false],
  ['s19', 'presenter', "We performed a five-centimeter resection and end-to-end anastomosis. Mochi recovered uneventfully and was discharged on day three.", [], false],
  ['s20', 'presenter', "Owner communication makes or breaks these cases. Be honest about the spectrum of outcomes from straightforward recovery to repeat surgery for complications.", [], false],
  ['s20', 'presenter', "My standard estimate range for a routine enterotomy at our institution is three thousand to five thousand dollars. Resection and anastomosis typically runs five to eight thousand.", [{ w: 12, kind: 'uncertain' }], false],
  ['s21', 'presenter', "A few closing pearls. Always palpate the entire bowel before closing — second foreign bodies are not rare and they will ruin your recovery.", [], false],
  ['s21', 'presenter', "Lavage copiously with warm saline before closing. Three to five liters is not excessive in a contaminated case.", [], false],
  ['s21', 'presenter', "Trust your gut on viability. If you're not sure the tissue is healthy, resect. The cost of an unnecessary resection is far less than the cost of dehiscence.", [], true],
  ['s22', 'moderator', "Thank you Dr. Mueller. We have several questions from the audience. The first is from Dr. Sandra Bell — how do you handle a foreign body that has migrated to the colon?", [], false],
  ['s22', 'presenter', "Great question Sandra. Colonic foreign bodies are uncommon but when they occur I generally still recommend laparotomy with a colotomy rather than per-rectum retrieval unless the object is at the rectal vault.", [], false],
  ['s22', 'moderator', "Next question from Dr. Mark Trent — what's your protocol for the patient who vomits the moment you start their post-op feeding trial?", [], false],
  ['s22', 'presenter', "Hold food for another twelve hours, run a CBC and chem panel looking for inflammation or electrolyte derangement, give a dose of maropitant, and try again. Persistent vomiting after twenty-four hours warrants imaging.", [{ w: 24, kind: 'uncertain' }], false],
  ['s23', 'presenter', "All the references for today's talk are listed on this slide and will be available in the VIN session library along with the recording.", [], false],
  ['s24', 'presenter', "Thank you so much for your attention. I'll stay on the line for a few minutes if anyone has individual questions.", [], false],
  ['s24', 'moderator', "Thank you Dr. Mueller. CE credit attestation is now open in the session toolbar. This session is worth one point five CE hours.", [], false],
  ['s24', 'moderator', "Have a great rest of your day everyone.", [], false],
];

export interface Segment {
  id: string;
  idx: number;
  start: number;
  end: number;
  speaker: SpeakerKey;
  slide_id: string | null;
  text: string;
  ai_flags: AiFlag[];
  needs_review: boolean;
  has_user_override: boolean;
  confidence: 'low' | 'normal';
  corrections: unknown[];
  // Optional real-data fields populated when the segment came from the live
  // backend instead of the fixture. When present, components prefer these
  // over the fixture SPEAKERS[seg.speaker] lookup so real speaker rosters
  // render correctly. See speakerDisplay() below.
  speaker_id?: string | null;
  speaker_name?: string | null;
  speaker_short?: string | null;
  speaker_color?: string | null;
  speaker_role?: string | null;
}

export interface SpeakerDisplay {
  short: string;
  name: string;
  color: string;
  role: string;
}

// Deterministic pseudo-random (mulberry32) so reloads paint identical timings.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

export const SEGMENTS: readonly Segment[] = (() => {
  const rng = mulberry32(0xCEDA1A);
  let t = 12;
  return RAW_SEGMENTS.map((row, i) => {
    const [slide_id, speakerKey, text, ai_flags, needs_review] = row;
    const wordCount = text.split(/\s+/).length;
    const dur = Math.max(3, wordCount / 2.6 + (rng() * 1.2 - 0.6));
    const start = t;
    const end = +(t + dur).toFixed(2);
    t = end + 0.25;
    return {
      id: `seg_${String(i + 1).padStart(3, '0')}`,
      idx: i,
      start: +start.toFixed(2),
      end,
      speaker: speakerKey,
      slide_id,
      text,
      ai_flags: ai_flags || [],
      needs_review: !!needs_review,
      has_user_override: false,
      confidence: ai_flags && ai_flags.length > 1 ? 'low' : 'normal',
      corrections: [],
    };
  });
})();

export const TOTAL_DURATION = SEGMENTS.length ? SEGMENTS[SEGMENTS.length - 1]!.end + 6 : 0;

// Slide-accent palette (same 10-color array as components.jsx::SLIDE_PALETTE)
const SLIDE_PALETTE = ['#2563eb', '#7c3aed', '#059669', '#d97706', '#dc2626', '#0891b2', '#6366f1', '#ea580c', '#0d9488', '#be185d'];
const _slideAccentMap = new Map(SLIDES.map((s, i) => [s.id, SLIDE_PALETTE[i % SLIDE_PALETTE.length]!]));
const _slideByIdMap = new Map(SLIDES.map(s => [s.id, s]));

// Deterministic FNV-1a-ish hash so any string (UUID, slug, fixture id) maps to
// a stable palette index. Used as fallback when a slide id isn't in the fixture
// map — real backend slides have UUIDs, not s01/s02/etc.
function _hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function slideAccent(slideId: string | null | undefined): string {
  if (!slideId) return '#4D6995';
  const fromFixture = _slideAccentMap.get(slideId);
  if (fromFixture) return fromFixture;
  return SLIDE_PALETTE[_hashStr(slideId) % SLIDE_PALETTE.length]!;
}
export function slideById(slideId: string): Slide | undefined { return _slideByIdMap.get(slideId); }

// Resolve a segment's speaker display info. Prefers real fields embedded by
// EditorView.load (speaker_id/name/short/color/role) and falls back to the
// fixture SPEAKERS dict so the demo / fixture-only paths still render.
export function speakerDisplay(seg: Segment): SpeakerDisplay {
  if (seg.speaker_name || seg.speaker_short) {
    const color = seg.speaker_color
      || SLIDE_PALETTE[_hashStr(seg.speaker_id || seg.speaker_name || 'unknown') % SLIDE_PALETTE.length]!;
    const name = seg.speaker_name || seg.speaker_short || 'Speaker';
    const short = seg.speaker_short || (seg.speaker_name ? seg.speaker_name.split(/\s+/).slice(0, 2).join(' ') : 'Speaker');
    return { short, name, color, role: seg.speaker_role || '' };
  }
  const sp = SPEAKERS[seg.speaker];
  if (sp) return { short: sp.short, name: sp.name, color: sp.color, role: sp.role };
  return { short: 'Speaker', name: 'Speaker', color: '#4D6995', role: '' };
}
