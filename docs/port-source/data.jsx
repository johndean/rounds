/* eslint-disable no-undef */
// Sample veterinary CE webinar — "Surgical Approach to GI Foreign Body Removal"
// All fixture data: sessions list, slides, segments, chat, polls, corrections, SOP state.

const SPEAKERS = {
  presenter: { id: "sp1", name: "Dr. Pamela Mueller, DVM, DACVS", short: "Dr. Mueller", role: "Presenter", color: "#002855" },
  cohost:    { id: "sp2", name: "Dr. Reggie Okafor, DVM",        short: "Dr. Okafor", role: "Co-host",   color: "#007D61" },
  moderator: { id: "sp3", name: "Jenna Hsu, RVT (Moderator)",    short: "J. Hsu",     role: "Moderator", color: "#B9975B" },
};

const SLIDES = [
  { id: "s01", n: 1,  title: "Title — Surgical Approach to GI Foreign Body Removal", kind: "title" },
  { id: "s02", n: 2,  title: "Speaker Bio & Disclosures",                              kind: "bio" },
  { id: "s03", n: 3,  title: "Learning Objectives",                                    kind: "objectives" },
  { id: "s04", n: 4,  title: "Epidemiology of GI FB in Small Animals",                 kind: "data" },
  { id: "s05", n: 5,  title: "Common Foreign Bodies — Linear vs Discrete",             kind: "comparison" },
  { id: "s06", n: 6,  title: "Clinical Presentation",                                  kind: "list" },
  { id: "s07", n: 7,  title: "Diagnostic Imaging — Radiograph Patterns",               kind: "image" },
  { id: "s08", n: 8,  title: "Ultrasound Findings",                                    kind: "image" },
  { id: "s09", n: 9,  title: "Preoperative Stabilization",                             kind: "protocol" },
  { id: "s10", n: 10, title: "Anesthetic Plan & Monitoring",                           kind: "protocol" },
  { id: "s11", n: 11, title: "Surgical Site Preparation",                              kind: "list" },
  { id: "s12", n: 12, title: "Enterotomy — Technique & Closure",                       kind: "technique" },
  { id: "s13", n: 13, title: "Gastrotomy — Indications & Approach",                    kind: "technique" },
  { id: "s14", n: 14, title: "Resection & Anastomosis Decision Tree",                  kind: "flow" },
  { id: "s15", n: 15, title: "Closure Patterns — Comparison Study",                    kind: "data" },
  { id: "s16", n: 16, title: "Postoperative Care",                                     kind: "list" },
  { id: "s17", n: 17, title: "Complications — Dehiscence & Septic Peritonitis",        kind: "list" },
  { id: "s18", n: 18, title: "Case Study 01 — Sock Obstruction in a 4yo Lab",          kind: "case" },
  { id: "s19", n: 19, title: "Case Study 02 — Linear FB in a DSH",                     kind: "case" },
  { id: "s20", n: 20, title: "Owner Communication & Prognosis",                        kind: "list" },
  { id: "s21", n: 21, title: "Pearls & Pitfalls",                                      kind: "list" },
  { id: "s22", n: 22, title: "Q&A",                                                    kind: "qa" },
  { id: "s23", n: 23, title: "References",                                             kind: "refs" },
  { id: "s24", n: 24, title: "Thank You",                                              kind: "title" },
];

// Generate ~80 segments. Each segment ties to a slide via slide_id (some left null to demo "unassigned").
// Words include ai-flag indices for drift/uncertain/low_confidence.
const RAW_SEGMENTS = [
  // Slide 1 — opening
  ["s01", "moderator", "Good morning everyone and welcome to today's continuing education session on the surgical approach to gastrointestinal foreign body removal in small animals.", [], false],
  ["s01", "moderator", "I'm Jenna Hsu and I'll be moderating today's session. Before we begin, a reminder that this webinar is being recorded for the VIN library.", [], false],
  ["s01", "moderator", "Our presenter today is Dr. Pamela Mueller, a board-certified surgeon at the University of Wisconsin School of Veterinary Medicine.", [], false],
  ["s02", "presenter", "Thank you Jenna. It's a pleasure to be here. Before we dive in, a quick disclosure — I have no relevant financial relationships with any commercial entities.", [], false],
  ["s02", "presenter", "I've been practicing soft tissue surgery for fifteen years and gastrointestinal foreign body removal remains one of the most common procedures we perform.", [{ w: 18, kind: "uncertain" }], false],
  // Slide 3 — Learning objectives
  ["s03", "presenter", "By the end of this hour you should be able to recognize the four classic radiographic patterns of GI obstruction, decide between enterotomy and resection-anastomosis, and counsel owners on realistic prognosis.", [], true],
  ["s03", "presenter", "We'll cover the decision-making framework I use intraoperatively and walk through two case studies from our teaching hospital.", [], false],
  // Slide 4 — Epidemiology
  ["s04", "presenter", "Looking at our institutional data from 2019 through 2024 we saw roughly twelve hundred GI foreign body cases across companion animal species.", [{ w: 11, kind: "low_confidence" }], false],
  ["s04", "presenter", "Dogs accounted for about seventy-eight percent of cases, cats for nineteen percent, and the remaining three percent were small mammals or exotics.", [], false],
  ["s04", "presenter", "The peak incidence in dogs is between one and four years of age. In cats it's bimodal — young cats with string foreign bodies and senior cats with linear obstructions from thread.", [{ w: 24, kind: "drift" }, { w: 25, kind: "drift" }], true],
  // Slide 5 — common FBs
  ["s05", "presenter", "Foreign bodies fall broadly into two categories — discrete and linear. Discrete bodies are usually toys, bones, corn cobs, balls, rocks.", [], false],
  ["s05", "presenter", "Linear foreign bodies are far more dangerous because of the plication mechanism they cause. String, thread, fishing line, dental floss, and clothing all qualify.", [], false],
  ["s05", "presenter", "If you remember nothing else from today, remember this — never pull on a linear foreign body until you have confirmed it is not anchored proximally.", [], true],
  // Slide 6 — clinical presentation
  ["s06", "presenter", "Presenting signs depend on the level and completeness of obstruction. Proximal complete obstructions present with violent unproductive vomiting within hours.", [], false],
  ["s06", "presenter", "Distal or partial obstructions can be more insidious — intermittent vomiting, anorexia, and a slow decline over three to seven days.", [], false],
  ["s06", "presenter", "On physical exam you may palpate a discrete mass, detect bunched intestinal loops, or find a string anchored under the tongue in cats.", [{ w: 16, kind: "uncertain" }], false],
  ["s06", "cohost",    "Pam, can I jump in here? I want to emphasize that the sublingual exam is non-negotiable in any vomiting cat. We miss it routinely in practice.", [], false],
  ["s06", "presenter", "Absolutely. Every vomiting cat gets a sedated oral exam if you can't get a good look awake. Reggie that's a great point.", [], false],
  // Slide 7 — radiograph patterns
  ["s07", "presenter", "On survey radiographs we look for four patterns. Pattern one — discrete radiopaque foreign body, easiest case.", [], false],
  ["s07", "presenter", "Pattern two — gravel sign distal to the obstruction indicating chronicity. Pattern three — plication and gas pattern suggesting a linear foreign body.", [], false],
  ["s07", "presenter", "Pattern four — generalized ileus without an obvious cause. This is the trickiest and often requires contrast or ultrasound.", [], true],
  // Slide 8 — ultrasound
  ["s08", "presenter", "Ultrasound has largely replaced contrast studies in our institution. With a competent sonographer you can identify the obstruction site, assess wall thickness, and evaluate for free fluid.", [{ w: 22, kind: "uncertain" }], false],
  ["s08", "presenter", "Free abdominal fluid in this context is a red flag for perforation and converts the case from elective to emergency.", [], false],
  // Slide 9 — preop stabilization
  ["s09", "presenter", "Before you cut, stabilize. A bolus of balanced crystalloid at ten to twenty milliliters per kilogram over fifteen minutes corrects most cases of mild dehydration.", [], false],
  ["s09", "presenter", "Check electrolytes. Hypokalemia and hypochloremia are common with proximal obstructions and worsen anesthetic risk.", [], true],
  ["s09", "presenter", "Pre-emptive analgesia matters. I use methadone at point five milligrams per kilogram intramuscularly as part of premedication.", [{ w: 9, kind: "low_confidence" }], false],
  // Slide 10 — anesthesia
  ["s10", "presenter", "Our standard anesthetic protocol for GI surgery is methadone-midazolam premed, propofol induction, and isoflurane maintenance with an opioid CRI intraoperatively.", [], false],
  ["s10", "presenter", "Monitoring should include capnography, doppler or oscillometric blood pressure, ECG, and core temperature. These cases lose heat fast on the open abdomen.", [], false],
  ["s10", "cohost",    "I'll add — if you don't have a forced-air warming device, get one before you do another abdominal surgery. It's the single biggest equipment upgrade we've made.", [], false],
  // Slide 11 — surgical prep
  ["s11", "presenter", "Clip generously — xiphoid to pubis, well past the lateral midline on both sides. You will be surprised how often you need to extend the incision cranially or caudally.", [], false],
  ["s11", "presenter", "Three-stage prep with chlorhexidine scrub, alternating with alcohol, then a final paint. Draping should expose the entire ventral midline.", [], false],
  // Slide 12 — enterotomy
  ["s12", "presenter", "Enterotomy is the workhorse procedure. Choose an incision site on the antimesenteric border just distal to the foreign body in healthy-appearing tissue.", [], true],
  ["s12", "presenter", "I use a number eleven blade for the initial stab and extend with Metzenbaum scissors to a length adequate to deliver the foreign body without tearing.", [], false],
  ["s12", "presenter", "Closure is single-layer simple interrupted appositional with three-zero polydioxanone on a taper needle. Bite five millimeters from the cut edge with five millimeters between bites.", [{ w: 13, kind: "drift" }], false],
  ["s12", "presenter", "Some surgeons advocate for a Gambee pattern. The evidence does not show a meaningful difference in dehiscence rates so go with what gives you the most consistent technique.", [{ w: 6, kind: "uncertain" }], false],
  // Slide 13 — gastrotomy
  ["s13", "presenter", "Gastrotomy is indicated when the foreign body is gastric and cannot be retrieved endoscopically. Make your incision in a hypovascular area between the greater and lesser curvatures.", [], false],
  ["s13", "presenter", "Two-layer closure for gastrotomy — inverting Cushing or Lembert in the seromuscular layer over a simple continuous mucosal layer.", [], false],
  // Slide 14 — R&A
  ["s14", "presenter", "When do you resect versus repair? Three criteria push me toward resection — non-viability on assessment, perforation, or a closure that would compromise more than fifty percent of the lumen.", [], true],
  ["s14", "presenter", "Assess viability with the four C's — color, contractility, capillary perfusion, and pulsation in the mesenteric arcade. Pink, contractile, bleeding, and pulsing means leave it.", [{ w: 14, kind: "uncertain" }], false],
  ["s14", "presenter", "Dark purple, flaccid, non-bleeding, and absent pulse means resect. Equivocal cases — wait five minutes after pack-warming and reassess.", [], false],
  // Slide 15 — closure comparison
  ["s15", "presenter", "Our retrospective review of six hundred enterotomies showed no statistically significant difference between simple interrupted appositional and modified Gambee closures.", [{ w: 6, kind: "low_confidence" }], false],
  ["s15", "presenter", "Dehiscence rates were two point eight percent and three point one percent respectively, with a p value of zero point six four.", [], false],
  // Slide 16 — postop
  ["s16", "presenter", "Postoperative care — small frequent meals starting twelve to twenty-four hours after surgery, continued IV fluids until eating reliably, multimodal analgesia for at least seventy-two hours.", [], false],
  ["s16", "presenter", "I send everyone home on a five-day course of trazodone for sedation. Compliance with activity restriction is the single biggest driver of outcomes in my experience.", [{ w: 11, kind: "drift" }], true],
  // Slide 17 — complications
  ["s17", "presenter", "The two complications that will keep you up at night are dehiscence and septic peritonitis. They typically present three to five days postoperatively with sudden decompensation.", [], false],
  ["s17", "presenter", "Any patient that fails to progress as expected gets re-imaged. Free fluid plus clinical decline equals return to surgery — do not wait for confirmation.", [], false],
  // Slide 18 — case 1
  ["s18", "presenter", "Our first case — Murphy, a four-year-old neutered male Labrador, presented with a twenty-four-hour history of vomiting and one episode of bloody diarrhea overnight.", [], false],
  ["s18", "presenter", "Radiographs showed a discrete soft tissue opacity in the proximal jejunum with gas dilation orad to the obstruction. Surgery confirmed a child's sock causing complete obstruction.", [{ w: 19, kind: "uncertain" }], false],
  ["s18", "presenter", "Single enterotomy on the antimesenteric border, retrieval without resection, simple interrupted appositional closure. Discharged on day two, no complications at the two-week recheck.", [], false],
  // Slide 19 — case 2
  ["s19", "presenter", "Our second case — Mochi, a seven-year-old spayed female domestic shorthair, presented with three days of anorexia and intermittent vomiting.", [], false],
  ["s19", "presenter", "Sublingual exam revealed thread anchored at the base of the tongue. Radiographs showed classic plication. Ultrasound showed no free fluid so we proceeded to surgery the same day.", [], true],
  ["s19", "presenter", "At surgery we found the thread anchored sublingually and looping through approximately forty centimeters of jejunum with one focal area of full thickness compromise.", [{ w: 16, kind: "drift" }, { w: 17, kind: "drift" }], false],
  ["s19", "presenter", "We performed a five-centimeter resection and end-to-end anastomosis. Mochi recovered uneventfully and was discharged on day three.", [], false],
  // Slide 20 — owner communication
  ["s20", "presenter", "Owner communication makes or breaks these cases. Be honest about the spectrum of outcomes from straightforward recovery to repeat surgery for complications.", [], false],
  ["s20", "presenter", "My standard estimate range for a routine enterotomy at our institution is three thousand to five thousand dollars. Resection and anastomosis typically runs five to eight thousand.", [{ w: 12, kind: "uncertain" }], false],
  // Slide 21 — pearls
  ["s21", "presenter", "A few closing pearls. Always palpate the entire bowel before closing — second foreign bodies are not rare and they will ruin your recovery.", [], false],
  ["s21", "presenter", "Lavage copiously with warm saline before closing. Three to five liters is not excessive in a contaminated case.", [], false],
  ["s21", "presenter", "Trust your gut on viability. If you're not sure the tissue is healthy, resect. The cost of an unnecessary resection is far less than the cost of dehiscence.", [], true],
  // Slide 22 — Q&A
  ["s22", "moderator", "Thank you Dr. Mueller. We have several questions from the audience. The first is from Dr. Sandra Bell — how do you handle a foreign body that has migrated to the colon?", [], false],
  ["s22", "presenter", "Great question Sandra. Colonic foreign bodies are uncommon but when they occur I generally still recommend laparotomy with a colotomy rather than per-rectum retrieval unless the object is at the rectal vault.", [], false],
  ["s22", "moderator", "Next question from Dr. Mark Trent — what's your protocol for the patient who vomits the moment you start their post-op feeding trial?", [], false],
  ["s22", "presenter", "Hold food for another twelve hours, run a CBC and chem panel looking for inflammation or electrolyte derangement, give a dose of maropitant, and try again. Persistent vomiting after twenty-four hours warrants imaging.", [{ w: 24, kind: "uncertain" }], false],
  // Slide 23 — refs
  ["s23", "presenter", "All the references for today's talk are listed on this slide and will be available in the VIN session library along with the recording.", [], false],
  // Slide 24 — thank you
  ["s24", "presenter", "Thank you so much for your attention. I'll stay on the line for a few minutes if anyone has individual questions.", [], false],
  ["s24", "moderator", "Thank you Dr. Mueller. CE credit attestation is now open in the session toolbar. This session is worth one point five CE hours.", [], false],
  ["s24", "moderator", "Have a great rest of your day everyone.", [], false],
];

// Expand into segment objects with timing.
const SEGMENTS = (() => {
  let t = 12; // start at 12s (after intro music)
  return RAW_SEGMENTS.map((row, i) => {
    const [slide_id, speakerKey, text, ai_flags, needs_review] = row;
    const wordCount = text.split(/\s+/).length;
    // ~2.5 words/sec for natural pace
    const dur = Math.max(3, wordCount / 2.6 + (Math.random() * 1.2 - 0.6));
    const start = t;
    const end = +(t + dur).toFixed(2);
    t = end + 0.25; // brief pause between segments
    return {
      id: `seg_${String(i + 1).padStart(3, "0")}`,
      idx: i,
      start: +start.toFixed(2),
      end,
      speaker: speakerKey,
      slide_id,
      text,
      ai_flags: ai_flags || [],
      needs_review: !!needs_review,
      has_user_override: false,
      confidence: ai_flags && ai_flags.length > 1 ? "low" : "normal",
      corrections: [],
    };
  });
})();

const TOTAL_DURATION = SEGMENTS.length ? SEGMENTS[SEGMENTS.length - 1].end + 6 : 0;

// Chat messages — anchored to a segment id, with time offset
const CHAT = [
  { id: "c1", author: "Dr. Sandra Bell", anchor: "seg_004", t: 78, text: "Quick housekeeping — slides will be in the library tomorrow?", placed: true },
  { id: "c2", author: "Dr. Mark Trent", anchor: "seg_010", t: 152, text: "The bimodal point about cats is so important. We see this constantly with senior cats.", placed: true },
  { id: "c3", author: "Dr. Aliyah Khan", anchor: "seg_013", t: 198, text: "Concur — pulled a linear FB at the base of the tongue last week and almost regretted not sedating first.", placed: false },
  { id: "c4", author: "Dr. Patrick Long", anchor: "seg_018", t: 264, text: "Sublingual exam saves lives. Repeat after me.", placed: true },
  { id: "c5", author: "Dr. Emma Rivera", anchor: "seg_021", t: 312, text: "What's your threshold for adding a CT?", placed: false },
  { id: "c6", author: "Dr. Pamela Mueller", anchor: "seg_023", t: 340, text: "Emma — usually only when ultrasound is equivocal AND I'm strongly considering laparoscopy. Will cover briefly later.", placed: false },
  { id: "c7", author: "Dr. Jamie Forsythe", anchor: "seg_028", t: 428, text: "Forced-air warmer is the #1 ROI piece of equipment in our practice. Co-sign Reggie 100%.", placed: true },
  { id: "c8", author: "Dr. Aliyah Khan", anchor: "seg_034", t: 512, text: "Do you ever use a stapler for the enterotomy closure?", placed: false },
  { id: "c9", author: "Dr. Pamela Mueller", anchor: "seg_034", t: 522, text: "Personally no for routine enterotomies — staplers shine on R&A. Cost vs. benefit doesn't pencil out for a simple closure.", placed: false },
  { id: "c10", author: "Dr. Sandra Bell", anchor: "seg_047", t: 698, text: "The four C's framing is so clean. Stealing this for our service rounds.", placed: true },
  { id: "c11", author: "Dr. Mark Trent", anchor: "seg_055", t: 808, text: "Question for Q&A — how do you handle FBs in the colon?", placed: false },
  { id: "c12", author: "Dr. Emma Rivera", anchor: "seg_063", t: 902, text: "Saving the 'cost of unnecessary resection vs. dehiscence' line. Going on the wall.", placed: true },
];

const POLLS = [
  {
    id: "p1", anchor: "seg_009", t: 138, placed: true,
    question: "What's your institution's primary imaging modality for suspected GI FB?",
    options: [
      { id: "a", label: "Survey radiographs only",       votes: 142 },
      { id: "b", label: "Radiographs + ultrasound",       votes: 318 },
      { id: "c", label: "Ultrasound first",               votes: 64  },
      { id: "d", label: "CT first",                       votes: 18  },
    ],
    total: 542, status: "closed",
  },
  {
    id: "p2", anchor: "seg_032", t: 470, placed: true,
    question: "Preferred enterotomy closure pattern?",
    options: [
      { id: "a", label: "Simple interrupted appositional",     votes: 408 },
      { id: "b", label: "Modified Gambee",                     votes: 86  },
      { id: "c", label: "Simple continuous",                   votes: 22  },
      { id: "d", label: "Two-layer (inverting)",               votes: 12  },
    ],
    total: 528, status: "closed",
  },
  {
    id: "p3", anchor: "seg_062", t: 894, placed: true,
    question: "How long do you continue IV fluids postoperatively in an uncomplicated enterotomy?",
    options: [
      { id: "a", label: "Until eating reliably",   votes: 312 },
      { id: "b", label: "24 hours regardless",     votes: 96  },
      { id: "c", label: "48 hours regardless",     votes: 54  },
      { id: "d", label: "Until discharge",         votes: 78  },
    ],
    total: 540, status: "closed",
  },
];

// SOP — 8 stages with deterministic acceptance checks for each.
// Stage names match the production app (real-app screenshots) — NOT the SSOT draft.
// SSOT used Dev Batch / Wistia / Medical Review-first ordering; production uses
// Copy edit draft → Medical review → Copy edit final → CMS published → Captions.
const SOP_STAGES = [
  { id: "prep",        name: "Prep",                 order: 1,
    checks: ["Audio asset uploaded", "Slides extracted from PPTX", "Speaker roster confirmed", "Ingest pipeline complete"] },
  { id: "copy_draft",  name: "Copy edit (draft)",    order: 2,
    checks: ["Verbatim-minus-fillers pass complete", "All needs_review flags first-pass cleared", "Spelling/punctuation pass", "Discrepancies triaged"] },
  { id: "medical",     name: "Medical review",       order: 3,
    checks: ["Drug names verified against VIN drug index", "Dosages cross-checked", "Species/breed terminology validated", "Reviewer attestation"] },
  { id: "copy_final",  name: "Copy edit (final)",    order: 4,
    checks: ["Medical review notes incorporated", "Discrepancies under threshold (< 0.5%)", "Speaker labels finalized", "Final readthrough"] },
  { id: "cms",         name: "CMS published",        order: 5,
    checks: ["Metadata complete (title, presenter, taxonomy)", "Key-points layer authored", "Library taxonomy assigned", "CE hours computed and attested"] },
  { id: "captions",    name: "Captions on video",    order: 6,
    checks: ["SRT generated from finalized timing", "Wistia upload complete", "Caption sync verified at 3 sample points", "Player embed tested"] },
  { id: "qa",          name: "QA",                   order: 7,
    checks: ["End-to-end playback (3 spot checks)", "Mobile rendering verified", "Search indexing confirmed", "GCS G1–G14 checks pass"] },
  { id: "complete",    name: "Complete",             order: 8,
    checks: ["Live in VIN library", "Notification to presenter sent", "Audit ledger archived"] },
];

// Session list — varied stages
const SESSIONS = [
  { id: "se_001", code: "060524_Mueller",        title: "Surgical Approach to GI Foreign Body Removal",                   presenter: "Dr. Pamela Mueller",   duration: "1h 04m", recorded: "2026-05-14", stage: "copy_draft", progress: 38, attendees: 612, needsReviewCount: 7,  presence: ["JH","RO","KS"], status: "active", segs: 66,  words: 6240, avgConf: 82, alignment: 100, coverage: "24/24" },
  { id: "se_002", code: "010726_Pickles",        title: "Crafting a Neurodivergent Career in Veterinary Practice",         presenter: "Dr. Kirstie Pickles",  duration: "0h 58m", recorded: "2026-05-13", stage: "medical",    progress: 36, attendees: 489, needsReviewCount: 14, presence: ["KP","JH"], status: "active", segs: 73,  words: 6892, avgConf: 82, alignment: 100, coverage: "26/26" },
  { id: "se_003", code: "041526_JepsenGrant",    title: "Cage-Side Radiology Rounds: Various Cases",                       presenter: "Dr. Hiro Tanaka",      duration: "1h 12m", recorded: "2026-05-12", stage: "copy_final", progress: 62, attendees: 287, needsReviewCount: 2,  presence: ["HT"],      status: "active", segs: 120, words: 9120, avgConf: 78, alignment: 95,  coverage: "18/18" },
  { id: "se_004", code: "042326_Anaphylaxis",    title: "Anaphylaxis in the Emergency Setting",                            presenter: "Dr. Reggie Okafor",    duration: "0h 47m", recorded: "2026-05-11", stage: "qa",         progress: 88, attendees: 1024,needsReviewCount: 0,  presence: ["RO","JH","KS","MM"], status: "active", segs: 54,  words: 5612, avgConf: 91, alignment: 100, coverage: "14/14" },
  { id: "se_005", code: "050726_Cytology",       title: "Cytology of Cutaneous Round Cell Tumors",                         presenter: "Dr. Aliyah Khan",      duration: "1h 18m", recorded: "2026-05-09", stage: "captions",   progress: 72, attendees: 391, needsReviewCount: 1,  presence: ["AK","JH"], status: "active", segs: 132, words: 10240,avgConf: 84, alignment: 98,  coverage: "29/29" },
  { id: "se_006", code: "050726_OLeary",         title: "Feline Corneal Disease: Cats Are Not Small Dogs!",                presenter: "Dr. Patrick O'Leary",  duration: "1h 05m", recorded: "2026-05-08", stage: "cms",        progress: 80, attendees: 1208,needsReviewCount: 0,  presence: ["PL"],      status: "active", segs: 73,  words: 7104, avgConf: 88, alignment: 100, coverage: "21/21" },
  { id: "se_007", code: "050626_GeriPain",       title: "Pain Management in the Geriatric Cat",                            presenter: "Dr. Emma Rivera",      duration: "0h 51m", recorded: "2026-05-06", stage: "prep",       progress: 4,  attendees: 0,   needsReviewCount: 0,  presence: ["MM"],      status: "processing", segs: 0, words: 0, avgConf: 0, alignment: 0, coverage: "0/0" },
  { id: "se_008", code: "050526_ReproImg",       title: "Reproductive Imaging in the Bitch — Ultrasound Pearls",            presenter: "Dr. Jamie Forsythe",   duration: "0h 56m", recorded: "2026-05-05", stage: "complete",   progress: 100,attendees: 736, needsReviewCount: 0,  presence: [],          status: "complete",   segs: 88,  words: 7320, avgConf: 90, alignment: 100, coverage: "19/19" },
  { id: "se_009", code: "050326_Hypoadr",        title: "Hypoadrenocorticism — Atypical Presentations",                     presenter: "Dr. Marcus Yates",     duration: "1h 09m", recorded: "2026-05-03", stage: "complete",   progress: 100,attendees: 542, needsReviewCount: 0,  presence: [],          status: "complete",   segs: 108, words: 8540, avgConf: 89, alignment: 100, coverage: "23/23" },
  { id: "se_010", code: "050126_AvianBeak",      title: "Avian Beak & Nail Trimming — A Hands-On Refresher",                presenter: "Dr. Sunita Rao",       duration: "0h 39m", recorded: "2026-05-01", stage: "complete",   progress: 100,attendees: 218, needsReviewCount: 0,  presence: [],          status: "complete",   segs: 48,  words: 4180, avgConf: 87, alignment: 100, coverage: "12/12" },
];

// Discrepancies sample — pairs of base_text vs STT, classified
const DISCREPANCIES = [
  { id: "d1", seg: "seg_005", kind: "drift",        base: "fifteen years", stt: "fifty years",          meaningful: true,  status: "open" },
  { id: "d2", seg: "seg_008", kind: "punctuation",  base: "two thousand nineteen through two thousand twenty four", stt: "2019 through 2024", meaningful: false, status: "open" },
  { id: "d3", seg: "seg_010", kind: "drift",        base: "with string foreign bodies", stt: "with strings, foreign bodies", meaningful: true, status: "open" },
  { id: "d4", seg: "seg_025", kind: "filler",       base: "(removed: um)", stt: "um, methadone",        meaningful: false, status: "resolved" },
  { id: "d5", seg: "seg_033", kind: "low_confidence", base: "polydioxanone", stt: "poly-dioxa-known",   meaningful: true, status: "resolved" },
  { id: "d6", seg: "seg_038", kind: "drift",        base: "Cushing or Lembert", stt: "cushing or lambert", meaningful: true, status: "open" },
  { id: "d7", seg: "seg_041", kind: "drift",        base: "four C's", stt: "four sees",                 meaningful: true, status: "open" },
  { id: "d8", seg: "seg_045", kind: "filler",       base: "(removed: you know)", stt: "you know",        meaningful: false, status: "resolved" },
];

// Correction lineage — applied corrections (for audit ledger)
const CORRECTIONS = [
  { id: "cor_001", t: "2026-05-14T09:14:22Z", seg: "seg_005", type: "text_edit",            actor: "K. Schultz",  prior: "fifty years",          next: "fifteen years",       note: "Drift correction; cross-checked CV." },
  { id: "cor_002", t: "2026-05-14T09:18:01Z", seg: "seg_010", type: "annotation_add",        actor: "K. Schultz",  prior: null,                   next: "low_confidence",      note: "Marked low-confidence span." },
  { id: "cor_003", t: "2026-05-14T09:22:44Z", seg: "seg_018", type: "speaker_reassignment",  actor: "R. Okafor",   prior: "presenter",            next: "cohost",              note: "Re-attributed to Dr. Okafor." },
  { id: "cor_004", t: "2026-05-14T09:24:08Z", seg: "seg_033", type: "text_edit",            actor: "K. Schultz",  prior: "poly-dioxa-known",     next: "polydioxanone",       note: "Drug name normalized." },
  { id: "cor_005", t: "2026-05-14T09:31:12Z", seg: "seg_041", type: "mark_reviewed",         actor: "M. Mendez",   prior: null,                   next: null,                  note: null },
  { id: "cor_006", t: "2026-05-14T09:35:50Z", seg: "seg_047", type: "annotation_add",        actor: "K. Schultz",  prior: null,                   next: "uncertain",           note: "Marked 'fifty percent' as uncertain (audio dropout)." },
  { id: "cor_007", t: "2026-05-14T09:42:17Z", seg: "seg_012", type: "chat_insert",           actor: "K. Schultz",  prior: null,                   next: "anchor: seg_012",     note: "Anchored audience question to plication slide." },
  { id: "cor_008", t: "2026-05-14T09:48:33Z", seg: "seg_022", type: "slide_reassignment",    actor: "M. Mendez",   prior: "s07",                  next: "s08",                 note: "Ultrasound discussion belongs to slide 8." },
  { id: "cor_009", t: "2026-05-14T10:02:01Z", seg: "seg_048", type: "text_edit",            actor: "K. Schultz",  prior: "pack warming",         next: "pack-warming",        note: "Hyphenation pass." },
  { id: "cor_010", t: "2026-05-14T10:05:48Z", seg: "seg_055", type: "mark_reviewed",         actor: "M. Mendez",   prior: null,                   next: null,                  note: null },
  { id: "cor_011", t: "2026-05-14T10:11:09Z", seg: "seg_059", type: "annotation_add",        actor: "K. Schultz",  prior: null,                   next: "drift",               note: "Marked 'looping through' span." },
  { id: "cor_012", t: "2026-05-14T10:18:36Z", seg: "seg_063", type: "mark_reviewed",         actor: "M. Mendez",   prior: null,                   next: null,                  note: null },
];

// Improvement requests
const IMPROVEMENTS = [
  { id: "i1",  surface: "Editor / Slide Rail",       title: "Slide picker should support search by slide number",            author: "carlab@vin.com",  priority: "high", risk: "low",      status: "pending",   created: "2026-05-05T13:38:00Z", url: "https://vetinfo.share/imp/i1", area: "UX/UI", description: "Slide picker is hard to navigate past 30+ slides. Would be much faster to type the number." },
  { id: "i2",  surface: "Editor",                    title: "Loading indicator on editor",                                    author: "carlab@vin.com",  priority: "med",  risk: "low",      status: "rolled-out", created: "2026-05-05T13:23:00Z", url: "https://transcript.sof", area: "UX/UI", description: "Editor needs some kind of still loading / done loading indicator. Not sure if it's limitation of my browser/RAM or something server-side but when sessions open, I'm never quite sure if something's broken or if it just hasn't finished loading. It seems to be more of an issue on sessions with more slides and/or segments, but happens with any of them." },
  { id: "i3",  surface: "Editor / Playback",         title: "Video playback & scrubber sync drifts on long sessions",         author: "kschultz@vin.com", priority: "crit", risk: "low",      status: "rolled-out", created: "2026-04-26T13:34:00Z", url: "https://transcript.sof", area: "Bug",  description: "Reported drift up to 4s on sessions > 1h. Cause was a Date.now reference instead of the audio.currentTime API." },
  { id: "i4",  surface: "Editor / Performance",      title: "Slow & extremely laggy on long sessions",                        author: "kschultz@vin.com", priority: "crit", risk: "low",      status: "rolled-out", created: "2026-04-26T13:33:00Z", url: "https://transcript.sof", area: "Performance", description: "Sessions over 1h start hitching badly. P14 cache key fix + virtualization landed in r2." },
  { id: "i5",  surface: "Editor / Right Rail",       title: "Words per segment count visible on hover",                        author: "kschultz@vin.com", priority: "med",  risk: "low",      status: "rolled-out", created: "2026-04-26T13:32:00Z", url: "https://transcript.sof", area: "UX/UI", description: "Thought it was limited to ~60 words/segment but we have outliers >150. Showing this in the hover tooltip clarifies." },
  { id: "i6",  surface: "SOP",                       title: "Stage assignment carry-forward rules",                            author: "mmendez@vin.com",  priority: "crit", risk: "low",      status: "rolled-out", created: "2026-04-26T13:32:00Z", url: "https://transcript.sof", area: "Workflow", description: "Changing task assignees on Type defaults should propagate to in-flight sessions where the stage hasn't started yet." },
  { id: "i7",  surface: "Session Detail",            title: "Session detail page slides — domain shouldn't be configurable",   author: "carlab@vin.com",   priority: "low",  risk: "medium",   status: "rolled-out", created: "2026-04-26T13:31:00Z", url: "https://transcript.sof", area: "UX/UI", description: "Slides domain was exposed as a setting in one early build. Reverted to fixed value." },
  { id: "i8",  surface: "Sessions",                  title: "Remove dev batch column from sessions list",                      author: "kschultz@vin.com", priority: "med",  risk: "low",      status: "rolled-out", created: "2026-04-26T10:27:00Z", url: "https://transcript.sof", area: "UX/UI", description: "There is no 'dev batch' stage anymore — column was a v3 holdover." },
  { id: "i9",  surface: "Sessions",                  title: "Long slide titles get truncated mid-word",                        author: "carlab@vin.com",   priority: "med",  risk: "low",      status: "rolled-out", created: "2026-04-23T09:11:00Z", url: "https://transcript.sof", area: "UX/UI", description: "When slide titles are longer than ~50 chars they truncate at arbitrary points." },
  { id: "i10", surface: "Sessions",                  title: "No way to delete a session from the list",                        author: "mmendez@vin.com",  priority: "high", risk: "medium",   status: "rolled-out", created: "2026-04-23T09:10:00Z", url: "https://transcript.sof", area: "UX/UI", description: "No way to delete sessions without going into the session detail." },
  { id: "i11", surface: "Editor",                    title: "Title is included in slide assignment widget",                    author: "kschultz@vin.com", priority: "med",  risk: "critical", status: "rolled-out", created: "2026-04-22T11:24:00Z", url: "https://transcript.sof", area: "Bug",  description: "Looks like it's picking up the session title as slide 0 in a few cases." },
  { id: "i12", surface: "Sessions",                  title: "Session code not searchable",                                     author: "carlab@vin.com",   priority: "high", risk: "high",     status: "rolled-out", created: "2026-04-22T11:21:00Z", url: "https://transcript.sof", area: "UX/UI", description: "Session code is present but can't be searched on." },
  { id: "i13", surface: "Editor",                    title: "Editing a chunk reverts to original",                             author: "mmendez@vin.com",  priority: "crit", risk: "critical", status: "rolled-out", created: "2026-04-22T11:09:00Z", url: "https://transcript.sof", area: "Bug",  description: "I think this is already fixed — but reopening for tracking." },
  { id: "i14", surface: "Audit",                     title: "Audit trail has 'open in editor' link but it 404s sometimes",      author: "kschultz@vin.com", priority: "med",  risk: "low",      status: "rolled-out", created: "2026-04-22T11:04:00Z", url: "https://vetinfo.share/imp/i14", area: "Bug",  description: "When a session has been archived the jump-to-segment link 404s." },
];

window.MIC_DATA = {
  SPEAKERS, SLIDES, SEGMENTS, TOTAL_DURATION,
  CHAT, POLLS, SOP_STAGES, SESSIONS, DISCREPANCIES,
  CORRECTIONS, IMPROVEMENTS,
};
