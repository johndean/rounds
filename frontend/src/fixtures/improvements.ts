/**
 * IMPROVEMENTS fixture — verbatim from data.jsx lines 280-294.
 */
export interface ImprovementFixture {
  id: string;
  surface: string;
  title: string;
  author: string;
  priority: 'crit' | 'high' | 'med' | 'low';
  risk: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'under-review' | 'approved' | 'in-progress' | 'rolled-out' | 'declined' | 'archived';
  created: string;
  url: string;
  area: string;
  description: string;
}

export const IMPROVEMENTS: readonly ImprovementFixture[] = Object.freeze([
  { id: 'i1',  surface: 'Editor / Slide Rail',       title: 'Slide picker should support search by slide number',              author: 'carlab@vin.com',   priority: 'high', risk: 'low',      status: 'pending',    created: '2026-05-05T13:38:00Z', url: 'https://vetinfo.share/imp/i1', area: 'UX/UI',       description: 'Slide picker is hard to navigate past 30+ slides. Would be much faster to type the number.' },
  { id: 'i2',  surface: 'Editor',                    title: 'Loading indicator on editor',                                      author: 'carlab@vin.com',   priority: 'med',  risk: 'low',      status: 'rolled-out', created: '2026-05-05T13:23:00Z', url: 'https://transcript.sof',       area: 'UX/UI',       description: "Editor needs some kind of still loading / done loading indicator. Not sure if it's limitation of my browser/RAM or something server-side but when sessions open, I'm never quite sure if something's broken or if it just hasn't finished loading. It seems to be more of an issue on sessions with more slides and/or segments, but happens with any of them." },
  { id: 'i3',  surface: 'Editor / Playback',         title: 'Video playback & scrubber sync drifts on long sessions',           author: 'kschultz@vin.com', priority: 'crit', risk: 'low',      status: 'rolled-out', created: '2026-04-26T13:34:00Z', url: 'https://transcript.sof',       area: 'Bug',         description: 'Reported drift up to 4s on sessions > 1h. Cause was a Date.now reference instead of the audio.currentTime API.' },
  { id: 'i4',  surface: 'Editor / Performance',      title: 'Slow & extremely laggy on long sessions',                          author: 'kschultz@vin.com', priority: 'crit', risk: 'low',      status: 'rolled-out', created: '2026-04-26T13:33:00Z', url: 'https://transcript.sof',       area: 'Performance', description: 'Sessions over 1h start hitching badly. P14 cache key fix + virtualization landed in r2.' },
  { id: 'i5',  surface: 'Editor / Right Rail',       title: 'Words per segment count visible on hover',                          author: 'kschultz@vin.com', priority: 'med',  risk: 'low',      status: 'rolled-out', created: '2026-04-26T13:32:00Z', url: 'https://transcript.sof',       area: 'UX/UI',       description: 'Thought it was limited to ~60 words/segment but we have outliers >150. Showing this in the hover tooltip clarifies.' },
  { id: 'i6',  surface: 'SOP',                       title: 'Stage assignment carry-forward rules',                              author: 'mmendez@vin.com',  priority: 'crit', risk: 'low',      status: 'rolled-out', created: '2026-04-26T13:32:00Z', url: 'https://transcript.sof',       area: 'Workflow',    description: 'Changing task assignees on Type defaults should propagate to in-flight sessions where the stage hasn’t started yet.' },
  { id: 'i7',  surface: 'Session Detail',            title: 'Session detail page slides — domain shouldn’t be configurable', author: 'carlab@vin.com',   priority: 'low',  risk: 'medium',   status: 'rolled-out', created: '2026-04-26T13:31:00Z', url: 'https://transcript.sof',       area: 'UX/UI',       description: 'Slides domain was exposed as a setting in one early build. Reverted to fixed value.' },
  { id: 'i8',  surface: 'Sessions',                  title: 'Remove dev batch column from sessions list',                        author: 'kschultz@vin.com', priority: 'med',  risk: 'low',      status: 'rolled-out', created: '2026-04-26T10:27:00Z', url: 'https://transcript.sof',       area: 'UX/UI',       description: "There is no 'dev batch' stage anymore — column was a v3 holdover." },
  { id: 'i9',  surface: 'Sessions',                  title: 'Long slide titles get truncated mid-word',                          author: 'carlab@vin.com',   priority: 'med',  risk: 'low',      status: 'rolled-out', created: '2026-04-23T09:11:00Z', url: 'https://transcript.sof',       area: 'UX/UI',       description: 'When slide titles are longer than ~50 chars they truncate at arbitrary points.' },
  { id: 'i10', surface: 'Sessions',                  title: 'No way to delete a session from the list',                          author: 'mmendez@vin.com',  priority: 'high', risk: 'medium',   status: 'rolled-out', created: '2026-04-23T09:10:00Z', url: 'https://transcript.sof',       area: 'UX/UI',       description: 'No way to delete sessions without going into the session detail.' },
  { id: 'i11', surface: 'Editor',                    title: 'Title is included in slide assignment widget',                      author: 'kschultz@vin.com', priority: 'med',  risk: 'critical', status: 'rolled-out', created: '2026-04-22T11:24:00Z', url: 'https://transcript.sof',       area: 'Bug',         description: "Looks like it's picking up the session title as slide 0 in a few cases." },
  { id: 'i12', surface: 'Sessions',                  title: 'Session code not searchable',                                       author: 'carlab@vin.com',   priority: 'high', risk: 'high',     status: 'rolled-out', created: '2026-04-22T11:21:00Z', url: 'https://transcript.sof',       area: 'UX/UI',       description: 'Session code is present but can’t be searched on.' },
  { id: 'i13', surface: 'Editor',                    title: 'Editing a chunk reverts to original',                               author: 'mmendez@vin.com',  priority: 'crit', risk: 'critical', status: 'rolled-out', created: '2026-04-22T11:09:00Z', url: 'https://transcript.sof',       area: 'Bug',         description: 'I think this is already fixed — but reopening for tracking.' },
  { id: 'i14', surface: 'Audit',                     title: "Audit trail has 'open in editor' link but it 404s sometimes",       author: 'kschultz@vin.com', priority: 'med',  risk: 'low',      status: 'rolled-out', created: '2026-04-22T11:04:00Z', url: 'https://vetinfo.share/imp/i14', area: 'Bug',        description: 'When a session has been archived the jump-to-segment link 404s.' },
]);
