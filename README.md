# Methionine Food Map · 甲硫氨酸食物地图

A bilingual (English / 简体中文), SEO-friendly **static** website showing the
methionine content and protein quality (DIAAS) of 84 common animal and plant
foods. Built with Python + Jinja2 — no Next.js, no runtime, no database.

- Every food gets its own crawlable static page in both languages
  (`/en/foods/{slug}/`, `/zh/foods/{slug}/`).
- Homepage ships the full food list as static HTML, with search, category /
  methionine-level filters, side-by-side compare, and a methionine-vs-DIAAS
  scatter plot layered on top via progressive-enhancement JavaScript.
- Generates `sitemap.xml` (with `hreflang` alternates), `robots.txt`, canonical
  URLs, `hreflang` (`en` / `zh-Hans` / `x-default`), and JSON-LD `Dataset`
  structured data on every page.

> This site is for educational purposes only and is not medical or dietary advice.
> 本网站仅用于教育和研究展示，不构成医疗或饮食建议。

## Project layout

```
foodmap-site/
├── build.py                # static-site generator (data/*.csv -> docs/)
├── scripts/
│   ├── prep_data.py        # builds the standardized bilingual data/foods.csv
│   ├── fetch_amino.py      # fetches the FULL amino-acid profile from USDA
│   └── retry_amino.py      # retries any foods fetch_amino.py missed
├── data/
│   ├── foods.csv           # master: names, categories, base aminos, DIAAS
│   ├── amino_full.csv      # full essential amino-acid profile (mg/g protein)
│   └── references.csv      # cited literature (Mathai/Bailey/Herreman/FAO/USDA)
├── .env                    # USDA_API_KEY=... (gitignored)
├── templates/              # Jinja2: base, index, food, explainer, references, root
├── static/                 # style.css, app.js (copied into docs/static/)
└── docs/                   # GENERATED OUTPUT — this is what GitHub Pages serves
```

The site ships per-food pages, a homepage (search / filter / compare / scatter),
a bilingual "What is DIAAS" explainer (`/<lang>/what-is-diaas/`), and a
References page (`/<lang>/references/`).

## 1. Install dependencies

Requires Python 3.9+.

```bash
cd foodmap-site
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
```

## 2. (Re)generate the data files — optional

All three data files are already included, so you can skip to step 3. Regenerate
only if the underlying data changes.

Base master (`data/foods.csv`) from the upstream amino-acid matrix:

```bash
python scripts/prep_data.py
# or: SOURCE_CSV=/path/to/food_amino_map.csv python scripts/prep_data.py
```

Full amino-acid profile (`data/amino_full.csv`) from USDA FoodData Central —
needs a free API key in `.env` as `USDA_API_KEY=...`
([get one here](https://fdc.nal.usda.gov/api-key-signup.html)):

```bash
python scripts/fetch_amino.py     # ~85 foods, validates each against stored Met
python scripts/retry_amino.py     # only if some foods failed (transient API errors)
```

DIAAS values and their citations live in `data/references.csv` and in the
`DIAAS_OVERRIDE` table at the top of `build.py` (e.g. potato, gelatin, soy
protein isolate, all sourced). Edit those to add or correct DIAAS data.

## 3. Build the site

Set `SITE_URL` to your real deployment URL so canonical links, `hreflang`,
sitemap, and `robots.txt` are correct. For GitHub Pages it is
`https://<user>.github.io/<repo>`.

```bash
SITE_URL="https://<user>.github.io/foodmap-site" python build.py
```

Output is written to `docs/`. (If you omit `SITE_URL` it defaults to a
placeholder — fine for a quick local look, wrong for production SEO.)

## 4. Preview locally

The site uses absolute URLs based on `SITE_URL`, so for a faithful local
preview build with a localhost URL and serve `docs/`:

```bash
SITE_URL="http://localhost:8000" python build.py
python -m http.server -d docs 8000
# open http://localhost:8000/   (redirects to /en/ or /zh/)
```

## 5. Deploy to GitHub Pages

1. Create a GitHub repo (e.g. `foodmap-site`) and push this project.
2. Build with the production URL and commit `docs/`:
   ```bash
   SITE_URL="https://<user>.github.io/foodmap-site" python build.py
   git add -A && git commit -m "Build site"
   git push
   ```
3. In the repo: **Settings → Pages → Build and deployment**, set
   **Source = Deploy from a branch**, **Branch = `main`**, **Folder = `/docs`**, Save.
4. Wait ~1 minute; your site is live at
   `https://<user>.github.io/foodmap-site/`.
5. After it's live, submit `https://<user>.github.io/foodmap-site/sitemap.xml`
   in [Google Search Console](https://search.google.com/search-console) to speed
   up indexing.

A user/organization root site (`<user>.github.io`) works too — just set
`SITE_URL="https://<user>.github.io"`.

> **Note:** `docs/` is regenerated from scratch on every build (the folder is
> wiped first). Don't hand-edit files inside it.

## Data & methodology

87 foods. Each carries a full essential amino-acid profile, a methionine level,
and (for 77 of them) a DIAAS value with its measurement method and source.

- **Amino acids** are milligrams **per gram of protein**, from USDA FoodData
  Central. Each food's full profile (His, Ile, Leu, Lys, Met, Cys, Phe, Tyr,
  Thr, Trp, Val, Arg, Gly) is fetched by `scripts/fetch_amino.py` and validated
  against the stored methionine value.
- **Methionine level** (lower / intermediate / higher) is assigned by tertiles of
  methionine content (mg/g protein). It is a neutral description of composition,
  **not** a health rating.
- **DIAAS** values each show a method label and a cited source:
  - Existing whole-food values: representative figures on the older-child/adult
    (>3y) reference pattern, compiled from Mathai 2017, Bailey 2020, FAO 2013.
  - Cited additions in `build.py` → `DIAAS_OVERRIDE` (potato, gelatin from
    Herreman 2020; soy protein isolate from Mathai 2017).
  - Insects (mealworm, cricket) from Hammer 2023, in-vitro DIAAS.
  - **Secondary measured values** (`build.py` → `ALT_DIAAS`): cooked-food DIAAS
    on the 6mo–3y pattern, shown as a labelled second line so they never
    overwrite the comparable value — pulses from Nosworthy 2017, cereals from
    Han 2019.
- The **FAO quality category** (excellent ≥100 / high 75–99 / no claim <75) is
  derived from DIAAS; foods with no published DIAAS are shown as such, never
  guessed.

### Where to add or correct data

- New foods: append to `data/foods.csv` and `data/amino_full.csv` (same slug).
- New / corrected DIAAS: edit `DIAAS_OVERRIDE` (primary) or `ALT_DIAAS`
  (secondary measured) at the top of `build.py`, with a method in `DIAAS_METHOD`.
- New citations: add a row to `data/references.csv` and reference its key.

Sources: USDA FoodData Central; FAO 2013; Mathai 2017; Bailey 2020;
Herreman 2020; Nosworthy 2017; Han 2019; Hammer 2023 — full citations on the
site's References page and in `data/references.csv`.
