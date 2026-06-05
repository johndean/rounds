# Phase 9 Research — Spellcheck Feasibility
Generated 2026-06-04. **NO CODE CHANGES.** Research only.

## TL;DR
**GO / NO-GO:** GO (limited scope)
**Recommended option:** Browser-native `spellcheck` attribute (already working) + **self-hosted LanguageTool (Docker)** with a **medical Hunspell dictionary supplement** for advanced grammar/term coverage. **LLM (Claude/Gemini) as opt-in "Polish" button** for sentence-level rewrite suggestions.
**Why:**
- **Grammarly Embedded SDK no longer exists.** It was discontinued Jan 10, 2024 and is non-functional in production apps — it is not an option in 2026.
- **PHI risk dominates.** Rounds processes medical transcripts. Any third-party cloud API (Sapling, LanguageTool Cloud, Grammarly Business, WProofreader Cloud) requires a BAA + Enterprise contract or it is non-compliant. Self-hosted LanguageTool keeps all text on infra we already own.
- **Cost stays near $0/mo at our scale.** Self-hosted LT (2 vCPU / 4 GB) fits an existing Railway-class box; medical Hunspell dictionary is GPL and free. Reserve LLM polish for human-triggered actions to bound cost.

---

## Grammarly Embedded SDK (deep dive)

### Product status (2026) — DEPRECATED, NON-FUNCTIONAL
- Grammarly publicly announced shutdown in July 2023; full discontinuation **January 10, 2024**.
- "Grammarly for Developers and the Text Editor SDK were discontinued on January 10, 2024, and will no longer work in apps."
- Grammarly redirected engineering to its core consumer product and GenAI features. **No replacement developer SDK has been released as of mid-2026.**
- The npm packages (`@grammarly/editor-sdk`, `@grammarly/editor-sdk-vue`, `@grammarly/editor-sdk-react`) are abandoned; last published versions remain (e.g. `editor-sdk-vue@2.5.5`) but the backend they call is shut down.
- **There is no path to integrate Grammarly into rounds in 2026 short of users installing the Grammarly browser extension themselves.**

### Pricing
- N/A — product does not exist. (Historically: free SDK with optional Premium upsell to end users.)

### Integration model
- Historically: `@grammarly/editor-sdk-vue/v3` exported `<GrammarlyEditorPlugin>` wrapping a contenteditable/textarea. Now non-functional.

### Security / PII / PHI
- Grammarly the **consumer product** is "HIPAA-aligned" only on **Enterprise** with a signed BAA. Free/Premium/standard Business tiers explicitly forbid PHI.
- The Embedded SDK never offered BAAs.
- Sources: Grammarly Support HIPAA article, accountablehq.com, paubox.com (2025 update).

### Performance
- Historically: debounced client-side checks with cloud round-trip; perceived latency ~200-500ms. Not testable today — backend is down.

### Vue 3 adapter availability
- Package exists on npm but the service it talks to is dead. **Effectively zero.**

---

## Alternatives — scored table

Scores: 1 = poor, 5 = excellent. Cost is at rounds scale (small team, < 100 copy-editors, < ~50M chars/mo).

| Option | Cost (rounds-scale) | Security (PHI) | Perf | Vue3 fit | Domain fit | Maturity |
|---|---|---|---|---|---|---|
| **Browser-native `spellcheck`** | $0 | 5 (no network) | 5 (instant) | 5 (attr only) | 2 (no medical terms; users add to OS dict) | 5 (browser) |
| **nspell + Hunspell + med dict** | $0 | 5 (client-side) | 4 (in-browser, ~5-15MB dict in RAM) | 4 (vanilla JS, wrap as composable) | 4 (drop in `hunspell-en-med-glut`, 90k medical terms) | 3 (mature lib, low activity) |
| **typo.js** | $0 | 5 | 3 (heavier hash map memory) | 3 | 4 (same Hunspell dicts) | 2 (~stagnant since ~2018) |
| **LanguageTool (self-host Docker)** | ~$5-15/mo infra (Railway/Fly small box) | 5 (on-prem; no PHI leaves) | 3 (server round-trip, debounce 500-1000ms) | 4 (REST POST `/v2/check`) | 4 (supports custom dictionaries + add-on rules) | 5 (active OSS, 25+ langs, n-gram models) |
| **LanguageTool Cloud / Premium** | $4.17-$19.90/user/mo + Premium API tier | 2 (no BAA available; PHI prohibited) | 4 | 4 | 4 | 5 |
| **proselint (wrapped)** | $0 self-host | 5 | 3 | 3 (need shim) | 1 (style/prose lint, not medical spell) | 3 (slow project velocity) |
| **Sapling API** | $0.025/1k chars (≈$2.50 / 100k words) | 2 (cloud; BAA only on enterprise; ask sales) | 4 | 4 (REST, JS sample) | 3 (custom-terms supported; medical not native) | 4 |
| **WProofreader (WebSpellChecker)** | Self-hosted Docker license (sales quote, 10-seat min for Business) | 4 (on-prem option exists) | 4 | 4 (official Vue/Quill/CKEditor adapters) | 4 (supports custom dictionaries; medical add-on) | 4 |
| **Microsoft Editor SDK** | n/a — not offered as embeddable SDK | 4 (if Azure tenant + BAA) | 4 | 2 (no Vue adapter; would call Azure REST) | 3 | 3 (consumer Editor + legacy Bing Spell Check API; Bing Spell Check retired) |
| **LLM (Claude Haiku / Gemini Flash / GPT-5-mini)** | ~$0.25-3 / M input tok, $1-15 / M output | 3-4 (Anthropic + Google offer BAAs on enterprise tier; OpenAI on ZDR/enterprise) | 1-2 (1-3s round trip; not keystroke) | 5 (plain HTTP) | 5 (any prompt, any domain) | 5 |

---

## Detailed per-alternative notes

### Browser-native `spellcheck="true"`
- Already works in rounds today (contenteditable default).
- **Zero PHI leakage** — runs entirely against the OS/browser dictionary. (Caveat: on some Chromium configs "enhanced spell check" sends text to Google. Setting `spellcheck="true"` + documenting that users should use *basic* spell check addresses this.)
- No grammar, no medical terms unless users right-click → "Add to dictionary."
- **Keep as the always-on baseline.**

### nspell + Hunspell (with medical dictionary supplement)
- `nspell` (wooorm) is a clean, plain-JS Hunspell implementation. Works in browser + Node.
- Pair with **`hunspell-en-med-glut`** (90,142 medical terms, GPL) or **`wordlist-medicalterms-en`** (98,119 terms).
- **Memory note:** JS Hunspell ports expand affixes upfront — peak RAM ~250-500MB observed for 60k-word en_US dict + medical. Acceptable on desktop, problematic on tablets. Mitigation: load on demand, use Web Worker.
- License: GPLv3 on medical dicts — this **forces dictionary distribution under GPL** but does NOT infect our application code if dict is loaded as data at runtime (standard interpretation; legal should confirm before ship).
- No grammar. Spell only.

### typo.js
- Older (Chris Finke, 2011). Still functional but stagnant. Same Hunspell-dictionary story as nspell, less active maintenance. **Prefer nspell.**

### LanguageTool (self-hosted, Docker) — RECOMMENDED FOR GRAMMAR LAYER
- OSS (LGPL). Java server. Public Docker images (`erikvl87/languagetool`, `meyay/languagetool`) listen on 8081.
- Resource footprint: 2 vCPU / 4 GB RAM is sufficient per maintainer guidance. Fits one Railway "small" instance (~$5-15/mo).
- API: `POST /v2/check` with `text=...&language=en-US`. Easy to wrap in a Vue composable + debounce (500-800ms).
- Custom dictionaries: supports user-level dictionary endpoints + custom rule XML. Medical Hunspell dict can be plugged as an additional spellcheck dictionary.
- **All text stays on infra we control.** No PHI leaves the VPC.
- Cloud LT API requires Premium ($4.99-24.90/mo) and has no BAA — **do not use cloud tier for medical**.

### LanguageTool Cloud / Premium
- API rate limits: free tier 20 req/min / 75k char/min per IP (insufficient + no BAA). Premium 80 req/min / 300k char/min. **No HIPAA BAA available** per current docs → blocked for medical content.

### Sapling
- Self-positioned as the Grammarly SDK successor; has explicit "Migrating from Grammarly Text Editor SDK" guide.
- Pricing: $0.025 / 1k chars first 10M, $0.02 / 1k chars after. ≈ $2.50 per 100k words.
- Has tone, AI detection, multilingual.
- **Security:** standard SOC 2; BAA only via enterprise sales — must negotiate before any PHI flows. **At our pre-scale stage this is friction.**

### WProofreader (WebSpellChecker)
- Direct Grammarly SDK replacement targeted at editors (CKEditor, TinyMCE, Quill, Froala). JS SDK available; would need light Vue 3 wrapper.
- Self-hosted Docker option (`webspellchecker/wproofreader`) → satisfies PHI containment.
- Pricing: opaque, sales-driven, 10-seat minimum for Business tier. **Probably overkill for current rounds team size.**

### LLM-based (Claude Haiku / Gemini Flash / GPT-5-mini)
- Cost example: Claude Haiku at $0.25/M in, $1.25/M out. A 500-word segment ≈ 700 tokens in + ~700 tokens out → ~$0.001 per pass. 10,000 passes/mo ≈ $10. Trivial.
- Latency 1-3s — **wrong tool for keystroke spellcheck**, right tool for an on-demand "Polish segment" button.
- BAA-capable: Anthropic offers BAA (Claude for Work / enterprise), Google offers BAA on Vertex AI. OpenAI BAA via Enterprise / ZDR. **All require enterprise-tier procurement.**
- Best-fit usage: post-edit polish, not live red-squiggle.

### proselint
- Style/prose linter, Python CLI. Catches weasel words, clichés, hedging. **Not a spellchecker, not medical-aware.** Optional add-on later, not a primary solution.

### Microsoft Editor SDK
- Not actually offered as an embeddable SDK for third-party web apps. Consumer-only.
- Bing Spell Check API (Azure Cognitive Services) is being retired / has been deprecated for new customers.
- **Skip.**

---

## Cost ballpark for rounds-sized usage

Assumptions: ~10 copy-editors, ~1000 transcript edits/day, average segment ~100 words, ~50M chars/mo of checkable text.

| Stack | Monthly cost |
|---|---|
| Browser-native only | **$0** |
| Browser-native + nspell+med dict (client-side) | **$0** |
| Browser-native + self-hosted LT Docker | **$5-15** (Railway small box) |
| Browser-native + self-hosted LT + LLM polish button (Claude Haiku, ~5k calls/mo) | **$10-25** |
| Sapling API (replacing all the above) | **~$1,250/mo** (50M chars × $0.025/1k) |
| WProofreader self-hosted | quote required; expect 4-low-5 figures/yr |
| Grammarly Embedded SDK | **N/A — discontinued** |

---

## Final recommendation

### GO/NO-GO: **GO** — but **NO-GO on Grammarly specifically** (product is dead).

### Recommended stack (in layers)
1. **Layer 1 — Always-on, free:** Confirm `spellcheck="true"` on all contenteditable + textarea surfaces. Document a "use basic browser spell check, not enhanced" recommendation for editors.
2. **Layer 2 — Grammar + medical terms:** **Self-hosted LanguageTool** (Docker) on a small Railway/Fly box. Add `hunspell-en-med-glut` (or `wordlist-medicalterms-en`) as a supplementary dictionary. Wrap with a debounced Vue 3 composable that calls our own `/api/lt/check` proxy (never the LT public cloud).
3. **Layer 3 — On-demand polish:** A user-triggered "Polish segment" button calling Claude Haiku (or Gemini Flash) **only when explicitly clicked**, gated behind a feature flag until a BAA is in place. Until BAA, gate to non-PHI test corpora.

### Reasoning (top 3)
1. **Grammarly Embedded SDK is gone** — re-confirmed across TechCrunch, AlternativeTo, vendor migration guides. Pursuing it is a non-starter.
2. **PHI containment is non-negotiable for medical transcripts.** Self-hosted LT is the only commercial-quality grammar engine that keeps text on our infra at zero per-character cost.
3. **Layered design preserves UX while bounding cost.** Native spellcheck gives instant red-squiggles; LT supplies grammar with ~500ms debounce; LLM polish is opt-in so cost is human-bounded, not keystroke-bounded.

### Open questions for stakeholder
- **BAA strategy:** Do we have BAAs in place with Anthropic / Google Vertex today? If not, is procurement willing to start one before Layer 3 ships?
- **GPL on medical dict:** Legal sign-off needed that loading a GPLv3 dictionary as runtime data does not require open-sourcing the rounds Vue app. (Standard interpretation says no, but get it in writing.)
- **Editor UX target:** Do we want underline-style inline marks (LT supports this with span-level offsets) or a sidebar issues panel? Affects integration scope.
- **Latency budget:** Confirm 500-800ms debounce is acceptable to copy-editors, or do they need <200ms (which forces nspell-in-Worker for spelling and LT for grammar only on blur)?
- **Scale ceiling:** Confirm the ~50M chars/mo assumption is current. If we expect 10x growth, self-hosted LT may need horizontal scaling.

---

## Source freshness audit
- Grammarly SDK deprecation: announced July 2023, executed Jan 2024 — *primary fact is >12mo old but stable and re-confirmed by 2026 migration guides (Sapling, WProofreader).*
- LanguageTool docs, pricing, Docker images: 2026 sources cited.
- LLM pricing: 2026 comparison aggregators.
- Hunspell medical dictionaries: GitHub projects active, last review 2024-2026.
- HIPAA / BAA stance for Grammarly: 2025 paubox update + Grammarly Support article (current).

## Sources
- [Grammarly to shut down the Text Editor SDK in January (TechCrunch)](https://techcrunch.com/2023/07/13/grammarly-to-shut-down-the-text-editor-sdk-in-january/)
- [Grammarly to discontinue Text Editor SDK (AlternativeTo)](https://alternativeto.net/news/2023/7/grammarly-to-discontinue-text-editor-sdk-shifts-focus-to-core-product-and-ai-integration/)
- [Migrating from Grammarly SDK (WProofreader Blog)](https://blog.wproofreader.com/migrating-from-grammarly-sdk-to-an-alternative-solution/)
- [Migrating from the Grammarly Text Editor SDK (Sapling docs)](https://sapling.ai/docs/sdk/Integration%20Details/grammarly-migration/)
- [Is Grammarly HIPAA compliant? (Grammarly Support)](https://support.grammarly.com/hc/en-us/articles/4403227220237-Is-Grammarly-HIPAA-compliant)
- [Is Grammarly HIPAA Compliant? No—Here’s What Healthcare Teams Need to Know (Accountable)](https://www.accountablehq.com/post/is-grammarly-hipaa-compliant-no-here-s-what-healthcare-teams-need-to-know)
- [Grammarly Security Compliances](https://www.grammarly.com/compliance)
- [LanguageTool — Style and Grammar Checker (GitHub)](https://github.com/languagetool-org/languagetool)
- [erikvl87/languagetool Docker image](https://hub.docker.com/r/erikvl87/languagetool)
- [Self-hosted grammar & spellcheck with LanguageTool (codeslikeaduck)](https://www.codeslikeaduck.com/posts/selfhostlanguagetool/)
- [Bring back free LanguageTool grammar checking by self-hosting (Ethan’s Wiki, 2026-05)](https://wiki.ethanppl.com/blog/2026/05/11/self-host-language-tools)
- [LanguageTool Public HTTP API](https://dev.languagetool.org/public-http-api.html)
- [LanguageTool Pricing 2026 (StackScored)](https://www.stackscored.com/pricing/grammar-proofreading/languagetool/)
- [Sapling API Pricing](https://sapling.ai/docs/api/pricing/)
- [Sapling Grammarly API alternative](https://sapling.ai/grammarly-api)
- [WProofreader SDK](https://wproofreader.com/sdk)
- [WebSpellChecker/wproofreader GitHub](https://github.com/WebSpellChecker/wproofreader)
- [nspell (Hunspell-compatible JS spell-checker)](https://github.com/wooorm/nspell)
- [Typo.js (cfinke)](https://github.com/cfinke/typo.js/)
- [hunspell-en-med-glut (medical dictionary)](https://github.com/glutanimate/hunspell-en-med-glut)
- [wordlist-medicalterms-en](https://github.com/glutanimate/wordlist-medicalterms-en)
- [OpenMedSpel for Hunspell](https://directory.fsf.org/wiki/OpenMedSpel_for_Hunspell)
- [LLM API Pricing 2026 (TLDL)](https://www.tldl.io/resources/llm-api-pricing-2026)
- [AI API Pricing Comparison (May 2026) (DevTk.AI)](https://devtk.ai/en/blog/ai-api-pricing-comparison-2026/)
- [5 Best Grammar and Spell Checking APIs / SDKs (Sapling)](https://sapling.ai/docs/api/comparison/)
