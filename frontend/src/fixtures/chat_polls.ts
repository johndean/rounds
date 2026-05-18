/**
 * Chat & Poll fixtures — verbatim port of docs/port-source/data.jsx lines 163-212.
 * Each chat message + poll has an `anchor` segment id and a `placed` flag.
 * Editor sub-tabs (Chat / Polls) read these; placement state lives in component state.
 */

export interface ChatMessage {
  id: string;
  author: string;
  anchor: string;
  t: number;
  text: string;
  placed: boolean;
}

export const CHAT: readonly ChatMessage[] = Object.freeze([
  { id: 'c1',  author: 'Dr. Sandra Bell',     anchor: 'seg_004', t: 78,  text: 'Quick housekeeping — slides will be in the library tomorrow?', placed: true  },
  { id: 'c2',  author: 'Dr. Mark Trent',      anchor: 'seg_010', t: 152, text: 'The bimodal point about cats is so important. We see this constantly with senior cats.', placed: true  },
  { id: 'c3',  author: 'Dr. Aliyah Khan',     anchor: 'seg_013', t: 198, text: 'Concur — pulled a linear FB at the base of the tongue last week and almost regretted not sedating first.', placed: false },
  { id: 'c4',  author: 'Dr. Patrick Long',    anchor: 'seg_018', t: 264, text: 'Sublingual exam saves lives. Repeat after me.', placed: true  },
  { id: 'c5',  author: 'Dr. Emma Rivera',     anchor: 'seg_021', t: 312, text: "What's your threshold for adding a CT?", placed: false },
  { id: 'c6',  author: 'Dr. Pamela Mueller',  anchor: 'seg_023', t: 340, text: 'Emma — usually only when ultrasound is equivocal AND I’m strongly considering laparoscopy. Will cover briefly later.', placed: false },
  { id: 'c7',  author: 'Dr. Jamie Forsythe',  anchor: 'seg_028', t: 428, text: 'Forced-air warmer is the #1 ROI piece of equipment in our practice. Co-sign Reggie 100%.', placed: true  },
  { id: 'c8',  author: 'Dr. Aliyah Khan',     anchor: 'seg_034', t: 512, text: 'Do you ever use a stapler for the enterotomy closure?', placed: false },
  { id: 'c9',  author: 'Dr. Pamela Mueller',  anchor: 'seg_034', t: 522, text: "Personally no for routine enterotomies — staplers shine on R&A. Cost vs. benefit doesn't pencil out for a simple closure.", placed: false },
  { id: 'c10', author: 'Dr. Sandra Bell',     anchor: 'seg_047', t: 698, text: "The four C's framing is so clean. Stealing this for our service rounds.", placed: true  },
  { id: 'c11', author: 'Dr. Mark Trent',      anchor: 'seg_055', t: 808, text: 'Question for Q&A — how do you handle FBs in the colon?', placed: false },
  { id: 'c12', author: 'Dr. Emma Rivera',     anchor: 'seg_063', t: 902, text: "Saving the 'cost of unnecessary resection vs. dehiscence' line. Going on the wall.", placed: true  },
]);

export interface PollOption {
  id: string;
  label: string;
  votes: number;
}

export interface Poll {
  id: string;
  anchor: string;
  t: number;
  placed: boolean;
  question: string;
  options: PollOption[];
  total: number;
  status: 'open' | 'closed';
}

export const POLLS: readonly Poll[] = Object.freeze([
  {
    id: 'p1', anchor: 'seg_009', t: 138, placed: true,
    question: "What's your institution's primary imaging modality for suspected GI FB?",
    options: [
      { id: 'a', label: 'Survey radiographs only', votes: 142 },
      { id: 'b', label: 'Radiographs + ultrasound', votes: 318 },
      { id: 'c', label: 'Ultrasound first',         votes: 64  },
      { id: 'd', label: 'CT first',                  votes: 18  },
    ],
    total: 542, status: 'closed',
  },
  {
    id: 'p2', anchor: 'seg_032', t: 470, placed: true,
    question: 'Preferred enterotomy closure pattern?',
    options: [
      { id: 'a', label: 'Simple interrupted appositional', votes: 408 },
      { id: 'b', label: 'Modified Gambee',                 votes: 86  },
      { id: 'c', label: 'Simple continuous',               votes: 22  },
      { id: 'd', label: 'Two-layer (inverting)',           votes: 12  },
    ],
    total: 528, status: 'closed',
  },
  {
    id: 'p3', anchor: 'seg_062', t: 894, placed: true,
    question: 'How long do you continue IV fluids postoperatively in an uncomplicated enterotomy?',
    options: [
      { id: 'a', label: 'Until eating reliably', votes: 312 },
      { id: 'b', label: '24 hours regardless',   votes: 96  },
      { id: 'c', label: '48 hours regardless',   votes: 54  },
      { id: 'd', label: 'Until discharge',       votes: 78  },
    ],
    total: 540, status: 'closed',
  },
]);
