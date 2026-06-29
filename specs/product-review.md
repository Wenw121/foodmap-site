# Product review — Protein Map / 蛋白质地图

PROD/BA pass over the existing site (bilingual DIAAS / amino-acid food reference, 112 foods,
static, deployed to GitHub Pages). Reviewed 2026-06-29. Scope of this doc: turn the work
already done + the open backlog into traceable stories with falsifiable ACs, a one-page PRD,
a RICE rank, and a story→metric matrix. Decisions (scope, rank, go/no-go) are handed back to
the owner, not made here.

---

## 0. What this product is

A search-entry reference: someone Googles a protein / amino-acid question, lands on a static
"door" page (quality-ranking hub, plant-protein hub, single-amino topic, aging background, or
a food page), and is funnelled into one interactive table (search · sort by any amino acid or
DIAAS · colour heatmap · compare up to 4). English and 简体中文, Google-targeted (not Baidu).

**Personas** (search intent → door):
- **P1 Macro/fitness searcher** — "best protein sources", "high protein foods" → quality-ranking hub
- **P2 Plant-based eater** — "best plant protein", "is X a complete protein" → plant-protein hub, food pages
- **P3 Amino-acid researcher / biohacker** — "methionine in foods", "lysine foods" → amino topic pages
- **P4 Longevity-curious reader** — "protein and aging", "methionine restriction" → aging page
- **P5 Chinese-language searcher (overseas, on Google)** — 蛋白质 / 氨基酸 queries → zh mirror

---

## 1. Outcome metrics (proposed — none exist yet)

The project has no instrumentation today, so these are **targets to install**, not live numbers.
One north star + supporting metrics. Each story below traces to exactly one.

| ID | Metric | Definition | Source once instrumented |
|----|--------|------------|--------------------------|
| M0 | **North star: monthly organic clicks** | Google → any page | Search Console |
| M1 | Indexed-page count | pages in Google's index vs 251 built | Search Console (Coverage) |
| M2 | Cluster impressions + avg position | for "best protein / plant protein / <amino> foods / DIAAS" | Search Console (Queries) |
| M3 | Tool-open rate | % of entry-page sessions that click "Open the interactive table" | analytics event |
| M4 | Food-page organic clicks | clicks landing on /foods/* | Search Console (Pages) |
| M5 | zh organic clicks | clicks on /zh/* (hreflang working) | Search Console (filter) |
| M6 | Compliance: health-claim leakage | # of pages/blurbs with a banned claim | build-time assertion (deterministic) |

**Measurement-readiness finding (blocker):** M0–M5 are all *blind* right now — a story can move
them, but no one can see it move. M6 is the only one verifiable today (templates are deterministic).
Installing M0–M5 is story S9/S10 and is the true prerequisite for the whole roadmap.

---

## 2. User stories (12) → metric

| # | Story | Metric |
|---|-------|--------|
| S1 | As P1, I search a head term and land on a list of foods **ranked by DIAAS** so I can see the best sources at a glance. | M2 |
| S2 | As any visitor, from a door page I can **open the interactive tool in one click** so I can explore beyond the static list. | M3 |
| S3 | As P2, I find plant foods **ranked by protein quality** so I can pick complete-ish plant proteins. | M2 |
| S4 | As P2, on a food page I can tell **whether it's a complete protein** (DIAAS + limiting AA). | M4 |
| S5 | As P3, I find foods **high or low in one specific amino acid** so I can target methionine/lysine/etc. | M2 |
| S6 | As P5, I get the **same content in 简体中文** with correct hreflang so Google serves the right language. | M5 |
| S7 | As any visitor, I can see the **data source per food** so I trust the numbers. | M4 |
| S8 | As P4, I read **protein-and-aging background with no medical claims** and a clear disclaimer. | M6 |
| S9 | As owner, my pages are **discoverable and indexed by Google**. | M1 |
| S10 | As owner, I can **see which pages and queries bring users** so I invest in what works. | M0 |
| S11 | As owner, the site lives on a **stable URL** so accrued ranking isn't lost to a later migration. | M1 |
| S12 | As any visitor on a phone, I can **use the table on mobile** (sort, compare, read the heatmap). | M3 |

Every story links to exactly one metric. Every metric M0–M6 has ≥1 story (no dead metric).

---

## 3. Acceptance criteria — top 4 stories

Each: happy path + one error/edge path + one NFR. Binary, observable.

### S1 — DIAAS-ranked landing (quality-ranking hub)
- **Happy:** Given a visitor opens `/{lang}/guides/protein-quality-ranking/`, When it loads, Then only foods with a published DIAAS appear, sorted descending, each showing its FAO tier (excellent ≥100 / high 75–99 / no-claim <75).
- **Error/edge:** Given a food has no DIAAS, When the ranking renders, Then it is **excluded** from the ranked list (never shown as `0` or blank-as-zero).
- **NFR (SEO):** `<title>` and `<h1>` contain the head keyword; canonical is self-referential; reciprocal `en↔zh` hreflang + `x-default` present and valid.

### S2 — One-click tool funnel
- **Happy:** Given any door page (hub / amino topic / aging / research), When it renders, Then a visible "Open the interactive table →" CTA links to `/{lang}/` (the tool).
- **Error/edge:** Given JavaScript is disabled, When the visitor clicks the CTA, Then they still reach the foods table page (the CTA is a real `<a href>`, not a JS handler).
- **NFR (mobile):** CTA tap target ≥44×44px and appears within the first viewport on a 375px-wide screen.

### S6 — Bilingual correctness
- **Happy:** Given a `/zh/` page, When rendered, Then all body copy is Chinese and the hreflang pair is reciprocal with a self-referential canonical.
- **Error/edge (hard constraint):** Given any `/en/` page, When rendered, Then it contains **no Chinese characters except the "中文" language switcher**. (Falsifiable regression check — currently passing.)
- **NFR:** sitemap lists both language URLs for every page; `x-default` resolves to the en URL.

### S8 — Aging background, no claims (compliance gate)
- **Happy:** Given the aging page, When rendered, Then findings are framed as association/preclinical and a disclaimer `<aside>` is present.
- **Error/edge + GATE:** Given any generated blurb or page copy, When scanned at build time, Then it contains **zero** banned claim tokens (prevents / cures / treats / "extends lifespan" / diagnoses). **Measurement:** build-time assertion over all rendered text. **Window:** every build. **Breach action:** build fails; offending string fixed before deploy.
- **NFR:** disclaimer present on every YMYL page (aging, cancer-research); every health statement carries a source link.

### AI Eval Card — N/A for v1
No story in this release involves nondeterministic AI behaviour (the blurb generator is
deterministic templates → covered by S8's Gherkin gate). **If** the planned in-page "ask the
data" AI Q&A is built, it would require this card before ship:

- **Confidence bands:** answers only from on-site food/amino data; if P(answer ∈ dataset) < 0.6 → refuse.
- **Refusal trigger:** any medical / dosage / "should I eat" question → refuse + link disclaimer.
- **Latency ceiling:** ≤ 5 s p95.
- **Fallback:** on refusal or timeout, link the relevant food page or the tool.
- **Numeric quality gate:** health-claim leakage ≤ 0.5% of sampled answers, sampled weekly; breach >0.5%/wk → disable the feature. False "complete protein" assertions: 0 tolerance.

---

## 4. RICE rank (backlog) — recommendation, not a decision

Confidence ∈ {10%, 50%, 80%, 100%}. Score = Reach × Impact × Confidence ÷ Effort (Effort in person-days).
Reach is relative (1–5, share of future visitors affected). Impact: 0.25/0.5/1/2/3.

| Item | R | I | C | E | Score | One-line rationale |
|------|---|---|---|---|-------|--------------------|
| A. Install measurement (GSC verify + privacy-light analytics + CTA event) | 5 | 3 | 80% | 1 | **12.0** | Unlocks M0–M5; without it nothing else is verifiable. |
| B. Decide+buy custom domain, migrate **before** indexing ramps | 5 | 2 | 50% | 1 | **5.0** | Cheap now; migrating after authority accrues forces re-index churn. |
| C. Submit sitemap + request indexing (needs A, ideally B first) | 5 | 3 | 80% | 0.5 | **24.0*** | Highest raw score but **gated** on A (and B for URL stability). |
| D. E-E-A-T page (About / methodology / who made this) | 3 | 2 | 50% | 1 | **3.0** | YMYL: aging/cancer pages need a credible author signal to rank at all. |
| E. Mini interactive preview embedded on door pages | 3 | 1 | 50% | 2 | **0.75** | Nice funnel boost; current CTA may already be enough. |
| F. Broaden Herreman / fill remaining blank cells | 1 | 0.5 | 50% | 1 | **0.25** | Marginal coverage; data already ~99% complete. |
| G. More long-tail hubs / amino pages | 3 | 1 | 50% | 2 | **0.75** | Scales reach later, only once A/C prove which clusters convert. |

*C's raw score is highest but it is a **dependency-gated** task, not a standalone winner — the
classic RICE trap. Do not read "C #1" as "do C first."

**Dependency / sequencing (what RICE misses):**
- A is the prerequisite for A→C and for proving D/E/G ever worked.
- B should precede C: indexing a `github.io` URL then moving domains wastes accrued signals.
- D matters disproportionately for the YMYL pages (aging, cancer) regardless of its low RICE.

**Recommended sequence (owner to confirm or override):** A → B → C → D → then E/G by what M2 shows → F last.

---

## 5. One-page PRD

**Problem.** High-quality DIAAS + amino data exists but is locked in PDFs/USDA tables with no
sortable, bilingual, source-labelled tool. Searchers can't compare protein *quality* anywhere.

**Who.** P1–P5 above. Primary: P1/P2 (head demand), P3 (winnable long tail), P5 (low-competition zh).

**Solution (shipped).** 251 static pages, 5 door types funnelling to one interactive table;
DIAAS ranking with FAO tiers; per-food source labels; secondary published DIAAS shown as a
labelled "Also measured" line (Nosworthy/Han/Herreman) without overwriting the comparable value.

**Why now.** No competitor offers a sortable DIAAS tool (DIAAS isn't in USDA data) — structural moat.

**Success.** M0 (organic clicks) trending up once measurement + indexing are live; M3 tool-open
rate proves the funnel; M6 stays at 0 leaked claims.

**Out of scope (v1):** user accounts, runtime API, Baidu/non-Google SEO, any medical-advice
feature, ads/monetization, recipes, real-time data sync.

**Risks.** (1) No measurement → flying blind [mitigation: item A]. (2) YMYL pages may never rank
for an anonymous site [item D]. (3) Domain migration churn [item B sequencing]. (4) Isolate-vs-food
data confusion [mitigated: form-matched labelling already enforced].

### Decision Memory
- Lead with DIAAS-ranked quality pages; volume in head phrases, winnability in "DIAAS". (validated via SERP, not volume tools)
- Data integrity: never overwrite a food's value with an isolate or a different age-pattern value; show as labelled secondary. (enforced in `ALT_DIAAS` / `ALT_METHOD`)
- Herreman 2020 added only form-matched (soy/whey isolate, pork); whole-food pages untouched.
- English pages carry no Chinese except the "中文" switcher. (hard constraint, regression-checked)
- Target Google only; Baidu out of scope.

---

## 6. Traceability matrix

| Metric | Stories moving it | Flag |
|--------|-------------------|------|
| M0 organic clicks | S10 | **blind** until A installed |
| M1 indexed pages | S9, S11 | **blind** until A; depends on B sequencing |
| M2 cluster position | S1, S3, S5 | **blind** until A |
| M3 tool-open rate | S2, S12 | **blind** until CTA event added (part of A) |
| M4 food-page clicks | S4, S7 | **blind** until A |
| M5 zh clicks | S6 | **blind** until A |
| M6 claim leakage | S8 | **live** (deterministic build check) |

- **No dead metrics** (every metric has ≥1 story).
- **No unlinked stories** (every story maps to one metric).
- **6 of 7 metrics are "blind"** — instrumented by item A. This is the single highest-leverage gap.

---

## 7. Handed back to the owner (decide; I only recommend)

1. **North-star metric** — confirm M0 (organic clicks) or pick another.
2. **The sprint cut / rank** — I recommend A→B→C→D; you choose what's in the next push.
3. **Domain go/no-go** — buy a custom domain now (recommended: before C), and which one.
4. **AI Q&A feature** — pursue the in-page Q&A (then the Eval Card binds), or leave it out of scope.
5. **Broaden Herreman to whole-food pages with explicit "(isolate)" labels** — yes/no.
