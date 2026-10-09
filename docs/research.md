# Research Findings — Link-Based Misinformation Verification & Propagation Tracker

Research date: **9 October 2026**. Every link below was opened or queried during research. Where a fact
comes only from third-party blogs (not the vendor/official source) it is marked **[unofficial]**.
Where we tested something live from our machine, it is marked **[tested 2026-10-09]**.

Hardware context for recommendations: team laptop, Windows 11, Python 3.11, **no NVIDIA GPU**. So every model
recommended here must run acceptably on CPU, or be optional.

---

## 0. Summary of what actually works today

| Platform | Download content | Search for similar posts (propagation) | MVP status |
|---|---|---|---|
| **YouTube** | ✅ yt-dlp (needs Deno JS runtime) [tested] | ✅ YouTube Data API v3, free 10k units/day ≈ 100 searches/day | **Supported** |
| **X / Twitter** | ✅ video via yt-dlp; tweet text via public embed endpoint [tested] — unofficial, see §1.3 | ⚠️ Official API is **paid only** (pay-per-use, $0.005/post read) | **Supported (content)**, propagation needs your approval for paid API |
| **Reddit** | ⚠️ unauthenticated JSON now **403** [tested]; oEmbed gives only title+author [tested]; full access needs approved OAuth app | ⚠️ same — needs approved OAuth app | **Partial** until Reddit approves an app |
| **Facebook** | ✅ public videos via yt-dlp [tested] | ❌ no public search API (CrowdTangle shut Aug 2024) | **Supported (public video only)** |
| **Instagram** | ❌ yt-dlp: "Instagram API is not granting access … use cookies" [tested] | ❌ | **Unsupported** (needs login → violates our rules) |
| **Any news article / blog URL** | ✅ HTML text extraction (trafilatura) | via GDELT | **Supported** |
| **Bluesky** | public post reads work | ❌ `searchPosts` anonymous → **403** [tested]; needs a (free) account | Planned |
| **Manual upload** (video/image/text) | ✅ | — | **Supported** (fallback for unsupported platforms) |

Biggest reality checks:
1. **Reddit closed anonymous access.** Our live request to `reddit.com/…/.json` returned HTTP 403 and gallery-dl
   reported "You've been blocked by network security". New API apps need manual approval under Reddit's
   Responsible Builder Policy (since Nov 2025) [unofficial: [redditapis.com](https://www.redditapis.com/blogs/reddit-data-api-2026), [replydaddy](https://replydaddy.com/blog/reddit-api-pre-approval-2025-personal-projects-crackdown)]. yt-dlp 2026.07.04 also *removed* Reddit login support ([releases](https://github.com/yt-dlp/yt-dlp/releases)).
2. **X has no free API tier for new developers** (pay-per-use since Feb 2026). Official pricing page:
   [docs.x.com pricing](https://docs.x.com/x-api/getting-started/pricing) — $0.005 per post read, 3M reads/month cap.
3. **Instagram content requires login** for yt-dlp in practice → unsupported.
4. **No free LLM is unlimited.** Gemini dropped Pro from its free tier; Groq free tier is rate-limited per model.
   A CPU-only laptop can run only small local LLMs slowly. This is the main architecture decision (see §8).

---

## 1. Content download

### 1.1 yt-dlp — recommended primary downloader
- Repo: <https://github.com/yt-dlp/yt-dlp> — Unlicense, ~196k stars, last push 2026-09-27. Latest release
  **2026.08.19** ([releases](https://github.com/yt-dlp/yt-dlp/releases)). Recent notes: Twitter broadcast fix,
  Instagram *logged-in* extraction fix, Reddit login removed (2026.07.04), Reddit unauthenticated fix (2026.06.09).
- **YouTube now needs an external JS runtime** ("EJS") since 2025.11.12; Deno is the only one enabled by default.
  Announcement: [yt-dlp issue #15012](https://github.com/yt-dlp/yt-dlp/issues/15012), component:
  [yt-dlp/ejs](https://github.com/yt-dlp/ejs). Install `yt-dlp[default]` + Deno ≥ 2.3. Without it we got
  the warning "YouTube extraction without a JS runtime has been deprecated" [tested].
- Live tests [tested 2026-10-09, yt-dlp 2026.08.19, no cookies]:
  - YouTube `jNQXAC9IVRw` → title/uploader/timestamp OK.
  - Facebook public watch video → OK.
  - X text-only tweet → "No video could be found in this tweet" (expected; video tweets go through yt-dlp, text via §1.3).
  - Instagram reel → "Instagram API is not granting access … use --cookies". **Unsupported without login.**
  - Reddit → 404/blocked.
- Also needs **ffmpeg** for audio extraction (not installed on our machine yet).

### 1.2 gallery-dl — images/galleries
- Repo: <https://github.com/mikf/gallery-dl> — GPL-2.0, last push 2026-10-03, v1.32.15 installed [tested].
  Release notes say active development moved to Codeberg ([releasebot](https://releasebot.io/updates/mikf/gallery-dl)).
- Useful for image posts (X image tweets, Imgur, etc.). Reddit blocked as above [tested].

### 1.3 X / Twitter text
- Official API: pay-per-use only for new developers; post read $0.005, monthly cap 3M reads, $20 credit
  promo after saving a card ([docs.x.com/pricing](https://docs.x.com/x-api/getting-started/pricing)). Free tier
  closed to new sign-ups 6 Feb 2026 [unofficial: [postproxy](https://postproxy.dev/blog/x-api-pricing-2026/)].
- The public embed endpoint `cdn.syndication.twimg.com/tweet-result` (used by X's own embedded-tweet widget)
  returns the tweet text, author, date and like count without login [tested]. It is **undocumented** and can
  change without notice. It is not a login bypass, but it is not an official API either → see decision D2 in §8.

### 1.4 Reddit
- Unauthenticated `.json` → 403 [tested]. `reddit.com/oembed?url=…` → 200 with title + author [tested].
- Official route: register an OAuth app and request approval; free tier is 100 QPM per OAuth client
  [unofficial: [prowlo](https://prowlo.com/blog/reddit-data-api), [creatorcrawl](https://creatorcrawl.com/blog/reddit-api-pricing-2026/)].
  Reddit's own Data API Wiki returned 403 to our fetcher, so we could not read it directly.
- **Recommendation:** apply for an approved Reddit app (free, non-commercial academic use) now; meanwhile Reddit
  is "partial" (title/author via oEmbed + manual upload of the media).

### 1.5 Article pages
- For news/blog URLs use **trafilatura** <https://github.com/adbar/trafilatura> (Apache-2.0, push 2026-10-06) for main-text extraction.

**Recommendation:** yt-dlp (+Deno, +ffmpeg) for video/audio, gallery-dl for images, trafilatura for articles,
X embed endpoint for tweet text (pending D2), Reddit oEmbed until approved, and **manual upload** as a
universal fallback so the demo never dead-ends.

---

## 2. Speech-to-text and OCR (Hindi + English)

### 2.1 Speech-to-text
| Option | Notes | Verdict |
|---|---|---|
| **faster-whisper** <https://github.com/SYSTRAN/faster-whisper> (MIT, push 2026-10-06) | CTranslate2 re-implementation of Whisper, up to ~4× faster than openai/whisper at same accuracy, int8 on CPU. Models on HF: `Systran/faster-whisper-small`, `-large-v3`; turbo CT2 conversion `deepdml/faster-whisper-large-v3-turbo-ct2` (HF, updated 2026-02). | **Recommended** (default `small` on CPU, `large-v3-turbo` if time allows) |
| openai/whisper <https://github.com/openai/whisper> | reference implementation, slower on CPU | baseline only |
| **Groq hosted Whisper** | `whisper-large-v3` and `-turbo` listed with 20 RPM / 2K RPD on Groq's plan table ([console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits)) | Optional fast path if we use Groq anyway |
| AI4Bharat **IndicConformer** `ai4bharat/indic-conformer-600m-multilingual` (MIT, HF updated 2026-10-08); repo <https://github.com/AI4Bharat/IndicConformerASR> | 22 Indian languages; strong on Indic benchmarks. NeMo-based, heavier install on Windows. | Future work / Hindi-only accuracy upgrade |
| IndicWhisper (Vistaar) — [arXiv 2305.15386](https://arxiv.org/abs/2305.15386), repo <https://github.com/AI4Bharat/vistaar> | Whisper-medium fine-tuned per language; lowest WER on 39/59 Vistaar benchmarks | Option for Hindi; per-language model |

Papers: Vistaar (Interspeech 2023) above; "Enhancing Whisper's Accuracy and Speed for Indian Languages through
Prompt-Tuning and Tokenization" (ICASSP 2025) [arXiv 2412.19785](https://arxiv.org/abs/2412.19785) — shows
tokenizer gains carry over to Faster-Whisper; a 2026 paper notes IndicConformer had no peer-reviewed paper as of
May 2026 ([arXiv 2605.03073](https://arxiv.org/abs/2605.03073)). Code-mixed Hinglish is a known weak spot for all of them.

### 2.2 OCR (images + video frames)
| Option | Hindi | Notes | Verdict |
|---|---|---|---|
| **EasyOCR** <https://github.com/JaidedAI/EasyOCR> (Apache-2.0, push 2025-12) | ✅ `Reader(['hi','en'])` | pip-only, PyTorch, works on CPU; slower, less maintained in 2026 | **Recommended for MVP** (simplest Windows install) |
| **PaddleOCR 3.x** <https://github.com/PaddlePaddle/PaddleOCR> (Apache-2.0, push 2026-09) | ✅ dedicated `devanagari_PP-OCRv5_mobile_rec` ([HF](https://huggingface.co/PaddlePaddle/devanagari_PP-OCRv5_mobile_rec)) — the generic PP-OCRv5 model is *not* good for Hindi | faster, more accurate; PaddlePaddle install is heavier | Upgrade option |
| Tesseract <https://github.com/tesseract-ocr/tesseract> | ✅ `hin` traineddata | needs native binary install on Windows; weaker on stylised social-media text | fallback |
| Surya <https://github.com/datalab-to/surya> | 90+ languages (Hindi quality not verified by us) | document-oriented (layout) | not chosen |

Video OCR plan: sample one frame every ~2 s, skip near-identical frames (perceptual hash), OCR the rest, dedupe lines.

---

## 3. Claim detection & extraction

- **CheckThat! Lab** (CLEF). 2025 lab overview: [arXiv 2503.14828](https://arxiv.org/abs/2503.14828). 2025 tasks:
  subjectivity, **claim normalization** (Task 2, 13 languages incl. Hindi), **numerical claim fact-checking**
  (Task 3), scientific discourse. Task 3 overview: [CEUR Vol-4038 paper 53](https://ceur-ws.org/Vol-4038/paper_53.pdf).
  Claim normalization finding: fine-tuned mT5/UMT5 beat zero-shot Qwen2.5, especially for Hindi
  ([MMA at CheckThat! 2025](https://ceur-ws.org/Vol-4038/paper_88.pdf)).
- **CheckThat! 2026** Task 2 = numerical claim verification by ranking LLM reasoning traces (English, Arabic). Example
  system: [DS@GT ARC, arXiv 2607.25069](https://arxiv.org/abs/2607.25069) — notably found sub-claim decomposition
  *did not help* there.
- Survey: "Claim Detection for Automated Fact-checking: monolingual, multilingual, cross-lingual"
  [arXiv 2401.11969](https://arxiv.org/abs/2401.11969).
- **ClaimBuster** (VLDB 2017 demo, [paper](https://www.vldb.org/pvldb/vol10/p1945-li.pdf), site
  <https://idir.uta.edu/claimbuster/>) — English-only check-worthiness scoring; free API key. Good English baseline,
  no Hindi.
- **Loki** ([arXiv 2410.01794](https://arxiv.org/abs/2410.01794), COLING 2025 demo; repo
  <https://github.com/Libr-AI/OpenFactVerification>, MIT): pipeline *Decomposer → Check-worthiness → Query
  generator → Evidence retriever → Verifier*. This is the design we copy.
- **Factcheck-GPT / Factcheck-Bench** repo <https://github.com/yuxiaw/Factcheck-GPT> (Apache-2.0) — benchmark of
  decomposition + check-worthiness steps.

**Recommendation:** two-layer extractor:
1. *Rule layer (no API, explainable):* sentence split → tag sentences containing numbers/percentages/currency/dates
   (regex + `dateparser`), named entities, and attribution cues ("according to", "WHO says", "सरकार के अनुसार", …).
2. *LLM layer:* Loki-style prompt that decomposes text into atomic, self-contained, check-worthy claims (Hindi or
   English), normalised to English for search, keeping the original. The rule-layer tags are passed in as hints and
   used as a fallback when no LLM is available.

---

## 4. Automated fact verification / evidence retrieval

- **FEVER** (Thorne et al. 2018) → Wikipedia-only, synthetic; useful history, not our setting.
- **AVeriTeC** (real-world claims, web evidence, 4 labels: Supported / Refuted / Not Enough Evidence /
  Conflicting): dataset page <https://fever.ai/dataset/averitec.html> (CC BY-NC 4.0, 4,568 claims), paper
  [arXiv 2305.13117](https://arxiv.org/abs/2305.13117). **AVeriTeC 2025 shared task** required open-weight systems,
  < 1 min/claim: overview [ACL Anthology 2025.fever-1.15](https://aclanthology.org/2025.fever-1.15/), leaderboard
  <https://fever.ai/2025/task.html> — winner CTU AIC (long-context RAG, [arXiv 2508.04390](https://arxiv.org/abs/2508.04390));
  2nd **HerO 2** (Qwen3, [arXiv 2507.11004](https://arxiv.org/abs/2507.11004), code <https://github.com/ssu-humane/HerO>).
- **QuanTemp** (SIGIR 2024): 15,514 real numerical/temporal claims from 45 fact-checkers, True/False/Conflicting,
  [arXiv 2403.17169](https://arxiv.org/abs/2403.17169), repo <https://github.com/factiverse/QuanTemp>
  (CC BY-NC 4.0; includes BM25 top-100 evidence). Follow-up **QuanTemp++** with claim decomposition and leakage
  removal: [arXiv 2510.22055](https://arxiv.org/abs/2510.22055), <https://github.com/VenkteshV/QuanTemp_Plus>.
- **FIRE** (NAACL 2025 Findings): iterative retrieve-or-answer agent, similar accuracy at 7.6× lower LLM cost and
  16.5× lower search cost — [arXiv 2411.00784](https://arxiv.org/abs/2411.00784), <https://github.com/mbzuai-nlp/fire>.
- **DEFAME** (ICML 2025): multimodal (text+image) zero-shot fact-checking pipeline —
  [arXiv 2412.10510](https://arxiv.org/abs/2412.10510), <https://github.com/multimodal-ai-lab/DEFAME> (Apache-2.0).
- **OpenFactCheck** — modular framework mixing claim processor/retriever/verifier
  ([arXiv 2405.05583](https://arxiv.org/abs/2405.05583), <https://github.com/openfactcheck-research/openfactcheck>, AGPL-3.0).
- Surveys: "Generative LLMs in Automated Fact-Checking" (199 papers; v3 June 2026)
  [arXiv 2407.02351](https://arxiv.org/abs/2407.02351) — key practical finding: putting *all* evidence in one
  prompt usually beats verifying each piece separately; LLM confidence scores are unreliable.
  "Fact-Checking with LLMs" adaptive pipeline [arXiv 2601.02574](https://arxiv.org/abs/2601.02574).

**Recommendation (what we reuse, not re-train):**
1. Query generation (2–3 queries/claim, Loki/FIRE style; English + Hindi).
2. Retrieve from sources in §5, **fact-check sites first** (claim matching against existing fact-checks is the
   highest-precision signal).
3. Re-rank passages with a multilingual embedder (`BAAI/bge-m3` or `intfloat/multilingual-e5-base`, both on HF).
4. Verdict: LLM reads top-k passages in one prompt and must cite passage IDs (survey finding above). Offline
   fallback: multilingual NLI `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (MIT).
5. Numeric check: extract quantities from claim and evidence, compare with tolerance, report the mismatch.
6. **Hard rule:** no evidence passage above similarity threshold → `unverifiable`. A verdict without ≥1 cited
   URL is rejected by code, not just by prompt.

Labels we output: `supported`, `contradicted`, `conflicting`, `unverifiable` (maps to AVeriTeC's 4 labels).

---

## 5. Evidence sources (checked live where possible)

| Source | Access today | Limits / terms | Use |
|---|---|---|---|
| **Google Fact Check Tools API** `claims:search` ([docs](https://developers.google.com/fact-check/tools/api), [reference](https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search)) | Needs a **free Google Cloud API key** — keyless call returns 403 "unregistered callers" [tested] | Quota shown in Cloud Console (not published); Google API ToS | Matches claims to ClaimReview fact-checks incl. Indian IFCN members (Alt News, BOOM, Factly, Vishvas…) |
| **GDELT DOC 2.0 API** | No key [tested — returned Times of India results] | ~1 request / 5 s (server message says so) [tested]; article list covers most recent 3 months of window ([GDELT blog](https://blog.gdeltproject.org/doc-2-0-updates-1-5-year-searching-and-updated-mobile-interface/)) | News evidence + **coverage timeline for propagation** |
| **Indian fact-checker RSS** | Alt News, Factly, Vishvas News, Newschecker, The Quint WebQoof, India Today — all 200 with items [tested]; BOOM feed URL 404 | public RSS | Local fact-check index (embed & search) |
| **PIB RSS** (`pib.gov.in/RssMain.aspx`) | 200, 20 items [tested] | public | Official govt press releases |
| **PIB Fact Check** <https://factcheck.pib.gov.in/> | site 200 [tested]; no API/RSS found ([PIB FAQ](https://pib.gov.in/FAQ_fact.aspx)) | publishes mainly on X @PIBFactCheck | Indexed indirectly via Google Fact Check / news |
| **data.gov.in** OGD API | free key on registration; 230k+ datasets ([Wikipedia](https://en.wikipedia.org/wiki/Data.gov.in)) | per-dataset API | Stretch goal: specific stats (e.g. CPI) |
| **Tavily** web search | free **1,000 credits/month, no card** ([Tavily docs](https://docs.tavily.com/documentation/api-credits)) | basic search = 1 credit | General web + govt sites (`site:gov.in`) |
| Serper (Google SERP) | 2,500 free queries, likely one-time [unofficial] | — | alternative |
| Brave Search API | free tier replaced by $5 monthly credit, card required (Feb 2026) [unofficial: [implicator](https://www.implicator.ai/brave-drops-free-search-api-tier-puts-all-developers-on-metered-billing/)] | — | not chosen |
| NewsAPI.org / GNews | free = 100 req/day, dev/localhost only, delayed [unofficial] | not for public deploy | not needed (GDELT covers it) |

---

## 6. Propagation & coordinated-behaviour detection

Literature:
- **FakeNewsNet** (Shu et al.) repo <https://github.com/KaiDMML/FakeNewsNet> — last push 2022; depends on
  hydrating tweet IDs via the X API, which is now paid → **not reproducible for free today**.
- **Hierarchical propagation networks** (Shu, Mahudeswaran, Wang, Liu; [arXiv 1903.09196](https://arxiv.org/abs/1903.09196); macro/micro propagation features) — conceptual
  basis for our propagation features; needs full share cascades we cannot get.
- **CooRnet** <https://github.com/fabiogiglietto/CooRnet> — **archived** (CrowdTangle shut down Aug 2024).
- **CooRTweet** <https://github.com/nicolarighetti/CooRTweet> (CRAN v2.1.2; Righetti & Balluff, *Computational
  Communication Research* 2025, [article](https://journal.computationalcommunication.org/article/view/5698)) —
  platform-agnostic: links accounts that share the same/similar content within `time_window` (default 10 s)
  at least `min_repetition` times; output is a coordination network. **We port this logic to Python.**
- "Uncovering Coordinated Networks on Social Media" (Pacheco et al.) [arXiv 2001.05658](https://arxiv.org/abs/2001.05658) —
  similar-text linking per time bucket; MinHash/Jaccard 0.8 ≈ exact-duplicate results.
- Cross-platform CIB, 2024 US election, WWW 2025: [arXiv 2410.22716](https://arxiv.org/abs/2410.22716).
- TikTok CIB (video-first, near-duplicate similarity networks): [arXiv 2505.10867](https://arxiv.org/abs/2505.10867).
- Telegram+Reddit coordination via hourly windows + char-n-gram TF-IDF cosine (2026): [arXiv 2602.13333](https://arxiv.org/abs/2602.13333).
- "Flood" rule (>6 words, duplicated >10× by >2 accounts): [arXiv 2401.06205](https://arxiv.org/abs/2401.06205).
- Media near-duplicates: Meta **PDQ** (image) / **TMK+PDQF, vPDQ** (video) in <https://github.com/facebook/ThreatExchange>.
- MinHash LSH: **datasketch** <https://github.com/ekzhu/datasketch> (MIT, push 2026-08).

What is realistically possible (given §0):
| Signal | Source | Feasible? |
|---|---|---|
| Similar videos by other channels + upload times | YouTube Data API `search.list` (100 units each; 10k/day ≈ 100 searches) | ✅ free key |
| News coverage volume over time (burst) | GDELT timeline mode | ✅ no key |
| Similar posts on X + author + time | X API recent search (paid) | ⚠️ needs your approval |
| Similar posts / crossposts on Reddit | Reddit API | ⚠️ needs approved app |
| Repost counts | X embed endpoint (like/retweet counts), YouTube view counts | ✅ counts only |
| Full repost cascades / who-shared-from-whom | none of the platforms give this free today | ❌ future scope |

**Recommended method (explainable, no training):**
1. Build 2–3 search queries from the extracted claims/title/key transcript phrases.
2. Collect candidate posts `(platform, post_id, author, timestamp, text, url)` from available sources.
3. Similarity = max(MinHash Jaccard on char-shingles, cosine on `multilingual-e5` embeddings); keep ≥ threshold.
4. Bucket matches by time (1 h / 6 h / 24 h). **Burst score** = peak bucket count vs. median (robust z-score);
   also count distinct authors per window.
5. **Coordination flag** (CooRTweet-style): ≥ N distinct accounts posting near-identical content within
   `time_window`, repeated ≥ `min_repetition`. Report the account cluster, timeline chart, and links.
6. Output wording is cautious: "pattern consistent with coordinated spreading", never "bot network confirmed".

---

## 7. Datasets for evaluation

| Dataset | Task | Access / licence | Plan |
|---|---|---|---|
| **QuanTemp** | numerical claim verification (T/F/Conflicting) | GitHub, CC BY-NC 4.0, BM25 evidence included | **Main eval**: sample ~300 test claims, our verifier on supplied evidence → accuracy, macro-F1 |
| **AVeriTeC** dev | real-world claim verification, 4 labels | HF/fever.ai, CC BY-NC 4.0 | Secondary eval (subset) |
| CheckThat! check-worthiness (2022–2024 Task 1, English) | claim detection | CheckThat! repos | Eval claim extractor (F1 on check-worthy class) |
| **MMIFND** (MMCFND, [arXiv 2410.10407](https://arxiv.org/abs/2410.10407)) | Hindi + 6 Indic multimodal fake news | per paper | Optional Hindi sanity check |
| Factify 2 ([arXiv 2304.03897](https://arxiv.org/abs/2304.03897)) | multimodal (India/US) support/refute | on request | Optional |
| FakeNewsNet | propagation | tweet hydration needs paid X API | **Not feasible free** — documented as limitation |
| Synthetic propagation set | burst/coordination detection | we generate (inject coordinated bursts into real background posts collected from YouTube/GDELT) | Precision/recall of the burst & coordination flags |

All of these are non-commercial licences → fine for an academic project; must be credited in the report.

---

## 8. Decisions that need your approval

- **D1 – LLM for claim extraction + verdicts** (biggest trade-off):
  - (a) **Groq free tier** (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`: 30 RPM / 1K RPD / 200K tokens per day per
    model on the plan table — [docs](https://console.groq.com/docs/rate-limits)); also offers hosted Whisper. Free account, no card.
  - (b) **Gemini API free tier** (Flash / Flash-Lite only; limits shown only in AI Studio; reportedly cut to ~20
    RPD for newest Flash [unofficial]). We could not confirm from the rate-limit page how free-tier prompts are used; check Gemini API terms before sending user content.
  - (c) **Local via Ollama** (e.g. Qwen3-4B) — fully free/offline but slow on a CPU-only laptop (~tens of seconds per claim).
  - Recommendation: **(a) Groq** primary + **(c)-style offline fallback using NLI** (no LLM) so the system still works without keys.
- **D2 – X content:** use the undocumented public embed endpoint + yt-dlp for tweet content (free, public posts only,
  may break), and **skip X propagation search** unless you approve paid X API credits.
- **D3 – Reddit:** one of you applies for a Reddit API app (free, academic). Until approved, Reddit = partial.
- **D4 – Web framework:** FastAPI + Jinja2 templates + a little vanilla JS (background jobs, auto API docs).

Free API keys we will need (all free, each requires one of you to create an account — I will not create accounts):
1. **Groq API key** (LLM + optional hosted Whisper).
2. **Google Cloud API key** with *Fact Check Tools API* and *YouTube Data API v3* enabled.
3. **Tavily API key** (1,000 free searches/month).
4. Optional: Reddit OAuth app (after approval), data.gov.in key.
