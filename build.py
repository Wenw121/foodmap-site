#!/usr/bin/env python3
"""
Static-site generator for the bilingual Methionine Food Map.

Reads data/foods.csv (+ data/amino_full.csv, data/references.csv) and renders a
fully static, SEO-friendly site into docs/ (ready for GitHub Pages). Every food
has its own crawlable HTML page in both English and Chinese; the homepage ships
the full food list as static HTML and layers search / filter / compare / scatter
on top with progressive-enhancement JavaScript. Also generates bilingual
"What is DIAAS" explainer pages and a References page.

Usage:
    python build.py
    SITE_URL="https://USER.github.io/REPO" python build.py
"""
import csv
import json
import os
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent
DATA_CSV = ROOT / "data" / "foods.csv"
AMINO_CSV = ROOT / "data" / "amino_full.csv"
REF_CSV = ROOT / "data" / "references.csv"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "docs"

# IMPORTANT: set this to your real deployment URL (no trailing slash).
SITE_URL = os.environ.get("SITE_URL", "https://example.github.io/foodmap-site").rstrip("/")

LANGS = ["en", "zh"]
HTML_LANG = {"en": "en", "zh": "zh-Hans"}

DISCLAIMER = {
    "en": "This site is for educational purposes only and is not medical or dietary advice.",
    "zh": "本网站仅用于教育和研究展示，不构成医疗或饮食建议。",
}

# ---- DIAAS values added/overridden from cited literature ----
# slug -> (diaas, limiting_aa_code, [source_keys])
DIAAS_OVERRIDE = {
    "potato": ("100", "", ["herreman2020"]),
    "gelatin": ("2", "Trp", ["herreman2020"]),
    "soy-protein-isolate": ("90", "SAA", ["mathai2017"]),
}
# default basis for the pre-existing DIAAS values
DEFAULT_DIAAS_SOURCES = ["mathai2017", "bailey2020", "fao2013"]

# DIAAS measurement-method label per food (shown for transparency)
DIAAS_METHOD = {
    "en": {"default": "Compiled · older-child/adult (>3y) pattern",
           "herreman": "Review compilation (>3y)",
           "invivo_pig": "In vivo, growing pig",
           "invitro_insect": "In vitro DIAAS · 6mo–3y pattern"},
    "zh": {"default": "整理值 · 老年/成人（>3 岁）模式",
           "herreman": "综述整理值（>3 岁）",
           "invivo_pig": "体内 · 生长猪法",
           "invitro_insect": "体外 DIAAS · 6 月–3 岁模式"},
}
METHOD_FOR = {  # slug -> method key (else 'default' when DIAAS present)
    "potato": "herreman", "gelatin": "herreman", "soy-protein-isolate": "invivo_pig",
    "mealworm": "invitro_insect", "cricket": "invitro_insect",
}

# secondary MEASURED DIAAS (cooked, in vivo growing pig, 6mo–3y pattern),
# shown as an extra labelled line so it never overwrites the comparable value
ALT_DIAAS = {  # slug -> (diaas, limiting_aa, source_key)
    "black-beans": ("49", "SAA", "nosworthy2017"),
    "pinto-beans": ("60", "SAA", "nosworthy2017"),
    "kidney-beans": ("51", "SAA", "nosworthy2017"),
    "chickpeas": ("67", "Trp", "nosworthy2017"),
    "lentils": ("58", "SAA", "nosworthy2017"),
    "buckwheat": ("68", "SAA", "han2019"),
    "oats": ("43", "Lys", "han2019"),
    "brown-rice": ("42", "Lys", "han2019"),
    "white-rice": ("37", "Lys", "han2019"),
    "wheat-hard": ("20", "Lys", "han2019"),
    "millet": ("7", "Lys", "han2019"),
}
ALT_METHOD = {"en": "Measured · cooked · 6mo–3y reference pattern",
              "zh": "实测 · 熟制 · 6 月–3 岁参考模式"}

# ---- typical serving sizes (grams), approximate, for "protein per serving" ----
CATEGORY_SERVING = {
    "Animal · whey/dairy": 30, "Animal · eggs": 50, "Animal · red meat": 150,
    "Animal · processed meat": 50, "Animal · poultry": 150,
    "Animal · fish/seafood": 150, "Plant · legumes": 100, "Plant · grains": 50,
    "Plant · nuts": 30, "Plant · seeds": 20, "Plant · vegetables/algae": 100,
    "Spice · seasoning": 2, "Special · collagen": 10, "Special · insect": 30,
}
SERVING_OVERRIDE = {
    "whole-milk": 240, "greek-yogurt": 170, "egg-white": 33, "egg-yolk": 17,
    "whole-egg": 50, "whey-protein-isolate": 30, "soy-protein-isolate": 30,
    "spirulina-dried": 7, "soy-milk": 240, "nori-laver": 3, "wakame": 10,
    "kelp-kombu": 5,
}

# full amino-acid display order: (key, en, zh, is_essential)
FULL_AMINOS = [
    ("His", "Histidine (His)", "组氨酸 (His)", True),
    ("Ile", "Isoleucine (Ile)", "异亮氨酸 (Ile)", True),
    ("Leu", "Leucine (Leu)", "亮氨酸 (Leu)", True),
    ("Lys", "Lysine (Lys)", "赖氨酸 (Lys)", True),
    ("Met", "Methionine (Met)", "甲硫氨酸/蛋氨酸 (Met)", True),
    ("Cys", "Cysteine (Cys)", "半胱氨酸 (Cys)", False),
    ("Phe", "Phenylalanine (Phe)", "苯丙氨酸 (Phe)", True),
    ("Tyr", "Tyrosine (Tyr)", "酪氨酸 (Tyr)", False),
    ("Thr", "Threonine (Thr)", "苏氨酸 (Thr)", True),
    ("Trp", "Tryptophan (Trp)", "色氨酸 (Trp)", True),
    ("Val", "Valine (Val)", "缬氨酸 (Val)", True),
    ("Arg", "Arginine (Arg)", "精氨酸 (Arg)", False),
    ("Gly", "Glycine (Gly)", "甘氨酸 (Gly)", False),
]

# amino acids offered in the homepage filter: methionine plus others studied in
# cancer-metabolism research, limited to those USDA reports (no serine/glutamine)
AMINO_FILTER = [
    ("all", "All amino acids (total)", "全部氨基酸（总量）"),
    ("met", "Methionine", "甲硫氨酸"),
    ("cys", "Cysteine", "半胱氨酸"),
    ("gly", "Glycine", "甘氨酸"),
    ("leu", "Leucine", "亮氨酸"),
    ("bcaa", "BCAA", "支链氨基酸"),
    ("arg", "Arginine", "精氨酸"),
    ("lys", "Lysine", "赖氨酸"),
]

# amino-acid columns shown in the homepage table (short 3-letter codes are
# language-neutral). Each maps to a data-aa-<key> attribute on the row.
AMINO_COLS = [
    ("met", "Met"), ("cys", "Cys"), ("leu", "Leu"), ("bcaa", "BCAA"),
    ("arg", "Arg"), ("gly", "Gly"), ("lys", "Lys"),
]

# plain-language key for the abbreviations used in the table (code, en, zh)
ABBREVS = [
    ("Met", "Methionine", "甲硫氨酸（蛋氨酸）"),
    ("Cys", "Cysteine", "半胱氨酸"),
    ("Leu", "Leucine", "亮氨酸"),
    ("BCAA", "Branched-chain amino acids (leucine + isoleucine + valine)",
     "支链氨基酸（亮氨酸 + 异亮氨酸 + 缬氨酸）"),
    ("Arg", "Arginine", "精氨酸"),
    ("Gly", "Glycine", "甘氨酸"),
    ("Lys", "Lysine", "赖氨酸"),
    ("DIAAS", "Digestible Indispensable Amino Acid Score — a protein-quality score",
     "可消化必需氨基酸评分（衡量蛋白质量的指标）"),
]

# single-amino-acid topic pages (long-tail SEO: "foods high in X" / "富含X的食物")
AMINO_TOPICS = [
    {"key": "met", "slug": "methionine", "code": "Met",
     "name_en": "Methionine", "name_zh": "甲硫氨酸（蛋氨酸）",
     "blurb_en": "Methionine is an essential, sulfur-containing amino acid found in dietary protein. The table below ranks 112 common foods by their methionine content per gram of protein, highest first.",
     "blurb_zh": "甲硫氨酸（蛋氨酸）是一种含硫必需氨基酸，存在于膳食蛋白中。下表按每克蛋白中的甲硫氨酸含量，对 112 种常见食物从高到低排序。"},
    {"key": "lys", "slug": "lysine", "code": "Lys",
     "name_en": "Lysine", "name_zh": "赖氨酸",
     "blurb_en": "Lysine is an essential amino acid that is often the limiting amino acid in cereal grains. The table ranks 112 common foods by lysine per gram of protein, highest first.",
     "blurb_zh": "赖氨酸是一种必需氨基酸，在谷物中往往是限制性氨基酸。下表按每克蛋白中的赖氨酸含量，对 112 种常见食物从高到低排序。"},
    {"key": "leu", "slug": "leucine", "code": "Leu",
     "name_en": "Leucine", "name_zh": "亮氨酸",
     "blurb_en": "Leucine is an essential branched-chain amino acid (BCAA). The table ranks 112 common foods by leucine per gram of protein, highest first.",
     "blurb_zh": "亮氨酸是一种必需支链氨基酸（BCAA）。下表按每克蛋白中的亮氨酸含量，对 112 种常见食物从高到低排序。"},
    {"key": "bcaa", "slug": "bcaa", "code": "BCAA",
     "name_en": "BCAAs", "name_zh": "支链氨基酸",
     "blurb_en": "The branched-chain amino acids (BCAAs) are leucine, isoleucine and valine. The table ranks 112 common foods by total BCAAs per gram of protein, highest first.",
     "blurb_zh": "支链氨基酸（BCAA）指亮氨酸、异亮氨酸和缬氨酸。下表按每克蛋白中的支链氨基酸总量，对 112 种常见食物从高到低排序。"},
    {"key": "arg", "slug": "arginine", "code": "Arg",
     "name_en": "Arginine", "name_zh": "精氨酸",
     "blurb_en": "Arginine is a conditionally essential amino acid found in dietary protein. The table ranks 112 common foods by arginine per gram of protein, highest first.",
     "blurb_zh": "精氨酸是一种条件必需氨基酸，存在于膳食蛋白中。下表按每克蛋白中的精氨酸含量，对 112 种常见食物从高到低排序。"},
    {"key": "gly", "slug": "glycine", "code": "Gly",
     "name_en": "Glycine", "name_zh": "甘氨酸",
     "blurb_en": "Glycine is the simplest amino acid and is especially abundant in collagen-rich foods. The table ranks 112 common foods by glycine per gram of protein, highest first.",
     "blurb_zh": "甘氨酸是结构最简单的氨基酸，在富含胶原蛋白的食物中尤其丰富。下表按每克蛋白中的甘氨酸含量，对 112 种常见食物从高到低排序。"},
    {"key": "cys", "slug": "cysteine", "code": "Cys",
     "name_en": "Cysteine", "name_zh": "半胱氨酸",
     "blurb_en": "Cysteine is a sulfur-containing amino acid (conditionally essential). The table ranks 112 common foods by cysteine per gram of protein, highest first.",
     "blurb_zh": "半胱氨酸是一种含硫氨基酸（条件必需）。下表按每克蛋白中的半胱氨酸含量，对 112 种常见食物从高到低排序。"},
]
_TOPIC_FULL_KEY = {"met": "Met", "cys": "Cys", "leu": "Leu", "arg": "Arg", "gly": "Gly", "lys": "Lys"}
_HEAT_STOPS = [(125, 205, 135), (250, 224, 120), (242, 140, 130)]

def topic_raw(f, key):
    return f.get("BCAA") if key == "bcaa" else f["amino_full"].get(_TOPIC_FULL_KEY[key])

def heat_color(t):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    seg = 0 if t <= 0.5 else 1
    lt = t / 0.5 if t <= 0.5 else (t - 0.5) / 0.5
    a, b = _HEAT_STOPS[seg], _HEAT_STOPS[seg + 1]
    return "rgb(%d,%d,%d)" % (round(a[0] + (b[0] - a[0]) * lt),
                              round(a[1] + (b[1] - a[1]) * lt),
                              round(a[2] + (b[2] - a[2]) * lt))

# per-food data-source label (drives the attribution line on each food page)
SOURCE_LABEL = {
    "en": {"USDA": "USDA FoodData Central match",
           "FSANZ": "FSANZ Australian Food Composition Database (Release 3)"},
    "zh": {"USDA": "USDA FoodData Central 匹配项",
           "FSANZ": "FSANZ 澳洲食物成分数据库（Release 3）"},
}

LIMIT_LABEL = {
    "SAA": {"en": "Sulfur amino acids (Met+Cys)", "zh": "含硫氨基酸 (Met+Cys)"},
    "Lys": {"en": "Lysine", "zh": "赖氨酸"},
    "Trp": {"en": "Tryptophan", "zh": "色氨酸"},
}

QUALITY = {  # (min_diaas) -> key
    "excellent": {"en": "Excellent quality (DIAAS ≥100)", "zh": "优质蛋白（DIAAS ≥100）"},
    "high": {"en": "High quality (DIAAS 75–99)", "zh": "高质量蛋白（DIAAS 75–99）"},
    "noclaim": {"en": "No quality claim (DIAAS <75)", "zh": "不作质量声明（DIAAS <75）"},
}

STR = {
    "en": {
        "site_name": "Protein Map",
        "tagline": "Protein quality (DIAAS) and full amino-acid profiles of 112 common foods.",
        "intro": (
            "Protein quality (DIAAS) and the full amino-acid profile of 112 common "
            "animal and plant foods, side by side. Search, filter by category, and "
            "sort any column."
        ),
        "search_ph": "Search a food (e.g. salmon, tofu)…",
        "all_categories": "All categories", "all_bands": "All methionine levels",
        "th_food": "Food", "th_category": "Category", "th_band": "Methionine",
        "th_protein": "Protein (g/100g)", "th_met": "Methionine (mg/g protein)",
        "th_diaas": "DIAAS", "th_quality": "Quality", "th_compare": "Compare",
        "compare_title": "Comparison",
        "compare_hint": "Select up to 4 foods in the table to compare them here.",
        "compare_clear": "Clear", "scatter_title": "Amino acid vs DIAAS",
        "scatter_hint": "Each point is a food. X = the amino acid selected above (mg/g protein), Y = DIAAS. The map follows your filters. Hover for the name; click to open its page.",
        "grp_animal": "Animal", "grp_plant": "Plant", "grp_spice": "Spice", "grp_special": "Special",
        "amino_cols_note": "Each amino-acid cell is shaded by its amount within that column. Click any column header to sort.",
        "amino_group_label": "Amino acids (mg/g protein)",
        "scale_low": "low", "scale_high": "high",
        "abbr_title": "Abbreviations",
        "home_amino_browse_title": "Browse by amino acid",
        "unit_short": "mg/g protein",
        "amino_topic_note": "Ranked highest first; values are mg per gram of protein. Click a food for its full amino-acid profile.",
        "amino_topic_all": "← See all 112 foods",
        "no_results": "No foods match your filters.", "view": "View",
        "back_home": "← All foods", "amino_profile": "Full amino-acid profile",
        "th_value": "mg/g protein", "essential": "Essential",
        "diaas_section": "Protein quality (DIAAS)", "diaas_na": "No published DIAAS value",
        "diaas_na_note": "DIAAS requires ileal digestibility studies that have not been published for this food.",
        "limiting_aa": "First limiting amino acid", "quality_cat": "FAO quality category",
        "diaas_method_label": "Method", "also_measured": "Also measured",
        "related_title": "Related foods", "nav_guides": "Guides",
        "guides_title": "Protein-quality guides",
        "guides_intro": "Curated lists of foods by protein quality (DIAAS), food group, and methionine content — a quick way to find complete proteins, the best plant proteins, and more.",
        "bc_home": "Home", "bc_guides": "Guides",
        "kw_protein": "protein", "kw_amino": "amino acids",
        "kw_amino_content": "amino acid content",
        "home_h1": "Amino acid content & DIAAS protein quality of 112 foods",
        "home_title": "Protein Quality & DIAAS of 112 Foods — Amino Acid Comparison",
        "home_desc": "Compare the protein quality (DIAAS), full essential amino-acid profiles, and methionine content of 112 common animal and plant foods. Search, filter, and compare proteins side by side.",
        "fdc_source": "USDA FoodData Central match", "band_label": "Methionine (mg/g protein)",
        "protein_label": "Protein content", "per_serving": "Protein per serving",
        "serving_note": "≈ per typical serving",
        "diaas_source": "DIAAS source", "other_lang": "中文",
        "footer_data": "Amino-acid data: USDA FoodData Central and FSANZ (per food). DIAAS values from published literature — see References.",
        "nav_explainer": "What is DIAAS?", "nav_references": "References", "nav_foods": "Foods",
        "band": {"lower": "Lower methionine", "intermediate": "Intermediate methionine", "higher": "Higher methionine"},
        "na": "N/A",
        "ref_title": "References & data sources",
        "ref_intro": "DIAAS values on this site come from the peer-reviewed literature below; the amino-acid values shown are from USDA FoodData Central. The national and regional food-composition databases listed under data sources are additional authoritative references for the protein and amino-acid composition of foods. Existing whole-food DIAAS values are representative figures compiled from Mathai 2017, Bailey 2020, and FAO 2013.",
        "explainer_title": "What is DIAAS? A short guide to protein quality",
        "explainer_lead": "DIAAS is the modern standard for scoring how well a food's protein meets human amino-acid needs. Here's how to read every number on this site.",
        "explainer": [
            {"h": "What DIAAS measures", "p": [
                "DIAAS (Digestible Indispensable Amino Acid Score) is the protein-quality method recommended by the FAO in 2013. It compares the digestible essential amino acids a protein supplies against human requirements, using the true ileal (small-intestine) digestibility of each individual amino acid.",
                "The score equals 100 × the lowest ratio of (digestible amino acid supplied) to (amino acid required). The amino acid with that lowest ratio is the food's first limiting amino acid."]},
            {"h": "How to read the score", "p": [
                "The FAO defines three categories: DIAAS ≥100 is an excellent-quality protein, 75–99 is high quality, and below 75 carries no quality claim. Unlike the older PDCAAS, DIAAS is not capped at 100, so it separates strong proteins from one another."]},
            {"h": "The limiting amino acid", "p": [
                "A protein is only as useful as its scarcest essential amino acid relative to need. Grains are usually limited by lysine; legumes by the sulfur amino acids (methionine + cysteine). This is why combining complementary foods, such as rice with beans, raises the protein quality of the mixture."]},
            {"h": "DIAAS vs PDCAAS", "p": [
                "PDCAAS (1991) used whole-protein faecal digestibility and truncated scores at 1.0. DIAAS uses amino-acid-specific ileal digestibility and is not truncated, which describes high-quality proteins more accurately (Mathai 2017)."]},
            {"h": "About methionine on this site", "p": [
                "Alongside DIAAS, each food shows methionine in milligrams per gram of protein. Methionine is one of the sulfur amino acids and its content varies several-fold across foods. The lower / intermediate / higher labels describe composition only — they are not a health rating."]},
            {"h": "Caveats", "p": [
                "DIAAS values are measured for specific foods and forms, often in pig or human ileal studies; variety, cooking, and processing change them. The values here are representative, not exact for every preparation. Many whole foods — most vegetables, mushrooms, and spices — have no published DIAAS at all, and are shown as “no published value” rather than guessed."]},
        ],
        "nav_research": "Research",
        "home_research_cta": "Why these amino acids? Read the research background →",
        "ref_grp_quality": "Protein quality (DIAAS)",
        "ref_grp_cancer": "Amino acids in cancer-metabolism research",
        "ref_grp_data": "Food-composition data sources",
        "research_title": "Why these amino acids? Amino acids studied in cancer-metabolism research",
        "research_lead": "The food map lets you filter by methionine, cysteine, glycine, leucine, the branched-chain amino acids, arginine and lysine. Here is the research background on why those particular amino acids come up when scientists study how cancer cells use nutrients — and, just as importantly, what that research does not say.",
        "research_note": "This page summarises published laboratory and animal research. It is background information, not medical or dietary advice, and nothing here claims that any food, amino acid, or diet prevents, treats, or cures cancer. Most of this work is preclinical — done in cells and mice — and how it applies to people is still being studied. If you are living with cancer, please make food and treatment decisions together with your oncology team and a registered dietitian.",
        "research_sources": "Background drawn from Lieu et al. (2020) and Gao et al. (2019). Full citations:",
        "research": [
            {"h": "Why amino acids come up in cancer research", "p": [
                "Cancer cells divide quickly, and to build new cells they need a steady supply of amino acids — both as protein building blocks and as raw material for DNA, antioxidants, and energy. Since Otto Warburg's work nearly a century ago, researchers have mapped how tumours rewire their metabolism, and amino-acid handling is one of the pathways that is often changed (Lieu et al., 2020).",
                "Because of this, scientists have asked whether limiting the supply of specific amino acids can slow particular cancer cells in the laboratory. The amino acids below are the ones most discussed in that research and that this site has composition data for."]},
            {"h": "Methionine", "p": [
                "Methionine feeds the cell's main methyl-donor cycle, which dividing cells rely on heavily. In mouse cancer models, restricting dietary methionine slowed tumour growth and changed how the tumours responded to some chemotherapy and radiotherapy; the same short diet measurably shifted one-carbon metabolism markers in a small group of healthy volunteers (Gao et al., 2019).",
                "This is early research in animals and short-term human metabolism. It is not evidence that a low-methionine diet treats cancer in patients, and methionine is an essential amino acid that the body needs."]},
            {"h": "Cysteine", "p": [
                "Many tumour cells import cystine (the paired form of cysteine) to make glutathione, an antioxidant that protects them from a kind of cell death called ferroptosis. Limiting cysteine availability is therefore studied as a way to make some cancer cells more vulnerable in the laboratory (Lieu et al., 2020)."]},
            {"h": "Glycine and serine", "p": [
                "Glycine and serine supply the 'one-carbon units' that cells use to build DNA and methyl groups. This one-carbon metabolism is frequently rewired in fast-dividing cancers, which makes it a busy area of study (Lieu et al., 2020).",
                "This site reports glycine but not serine, because USDA FoodData Central does not list serine separately for most foods."]},
            {"h": "Leucine and the branched-chain amino acids (BCAAs)", "p": [
                "Leucine, isoleucine and valine are the branched-chain amino acids. Leucine in particular helps switch on the mTORC1 pathway, a master signal that tells cells to grow and make protein. BCAA metabolism is altered in several cancers, so it is studied both as a growth signal and as a possible target (Lieu et al., 2020)."]},
            {"h": "Arginine", "p": [
                "Some tumours lose the enzyme (ASS1) that lets cells make their own arginine, so they have to take it from the blood — a dependence called arginine auxotrophy. Researchers study this as a potential weak point that arginine-depleting drugs might exploit (Lieu et al., 2020)."]},
            {"h": "Lysine", "p": [
                "Lysine is included for a different, simpler reason: it is the amino acid that most often limits the protein quality of grains and many plant foods. Filtering by lysine helps explain why some plant proteins score lower on DIAAS, which is the main purpose of this site."]},
            {"h": "How this connects to the food map", "p": [
                "The filter on the home page lets you sort foods by any of these amino acids, measured in milligrams per gram of protein, and combine that with a minimum DIAAS. It is a way to explore the composition of foods — for example, to find higher-quality proteins that happen to be lower in methionine.",
                "The lower / intermediate / higher labels describe composition only. They are not a health rating, and a food being 'lower' or 'higher' in an amino acid says nothing on its own about whether it is good or bad for any person."]},
            {"h": "What this page is not", "p": [
                "It is not a diet plan, a cancer-prevention claim, or a treatment recommendation. Single nutrients behave very differently inside a whole diet and a whole body than they do in a dish of cells, and restricting essential amino acids can be harmful without medical supervision. Use this as background for understanding the data, and talk to qualified professionals about anything concerning your own health."]},
        ],
    },
    "zh": {
        "site_name": "蛋白质地图",
        "tagline": "112 种常见食物的蛋白质量（DIAAS）与完整氨基酸谱。",
        "intro": (
            "112 种常见动物与植物性食物的蛋白质量（DIAAS）与完整氨基酸谱，并排呈现。"
            "可搜索、按分类筛选、点任意列排序。"
        ),
        "search_ph": "搜索食物（如 三文鱼、豆腐）…",
        "all_categories": "全部分类", "all_bands": "全部甲硫氨酸水平",
        "th_food": "食物", "th_category": "分类", "th_band": "甲硫氨酸",
        "th_protein": "蛋白质 (g/100g)", "th_met": "甲硫氨酸 (mg/g 蛋白)",
        "th_diaas": "DIAAS", "th_quality": "质量档", "th_compare": "对比",
        "compare_title": "对比", "compare_hint": "在表格中最多勾选 4 种食物，在此并排对比。",
        "compare_clear": "清除", "scatter_title": "氨基酸 vs DIAAS",
        "scatter_hint": "每个点代表一种食物。X = 上方所选氨基酸（mg/g 蛋白），Y = DIAAS。分布图会跟随筛选条件更新。悬停看名称，点击进入详情页。",
        "grp_animal": "动物", "grp_plant": "植物", "grp_spice": "香料", "grp_special": "特殊",
        "amino_cols_note": "每个氨基酸格子按其在该列中的高低着色。点击任意表头即可排序。",
        "amino_group_label": "氨基酸（mg/g 蛋白）",
        "scale_low": "低", "scale_high": "高",
        "abbr_title": "缩写说明",
        "home_amino_browse_title": "按氨基酸浏览",
        "unit_short": "mg/g 蛋白",
        "amino_topic_note": "按从高到低排序；数值为每克蛋白中的毫克数。点击食物可查看完整氨基酸谱。",
        "amino_topic_all": "← 查看全部 112 种食物",
        "no_results": "没有符合筛选条件的食物。", "view": "查看",
        "back_home": "← 全部食物", "amino_profile": "完整氨基酸谱",
        "th_value": "mg/g 蛋白", "essential": "必需",
        "diaas_section": "蛋白质量（DIAAS）", "diaas_na": "暂无已发表的 DIAAS 值",
        "diaas_na_note": "DIAAS 需要回肠消化率实验数据，该食物尚无已发表研究。",
        "limiting_aa": "第一限制性氨基酸", "quality_cat": "FAO 质量等级",
        "diaas_method_label": "测定方法", "also_measured": "另有实测值",
        "related_title": "相关食物", "nav_guides": "指南",
        "guides_title": "蛋白质量指南",
        "guides_intro": "按蛋白质量（DIAAS）、食物类别与甲硫氨酸含量整理的食物清单——快速找到完整蛋白、最佳植物蛋白等。",
        "bc_home": "首页", "bc_guides": "指南",
        "kw_protein": "蛋白质", "kw_amino": "氨基酸",
        "kw_amino_content": "氨基酸含量",
        "home_h1": "112 种食物的氨基酸含量与 DIAAS 蛋白质量",
        "home_title": "112 种食物的蛋白质量与 DIAAS — 氨基酸对比",
        "home_desc": "对比 112 种常见动物与植物性食物的蛋白质量（DIAAS）、完整必需氨基酸谱与甲硫氨酸含量。可搜索、筛选并并排比较。",
        "fdc_source": "USDA FoodData Central 匹配项", "band_label": "甲硫氨酸 (mg/g 蛋白)",
        "protein_label": "蛋白质含量", "per_serving": "每份蛋白质",
        "serving_note": "≈ 每份常见食用量",
        "diaas_source": "DIAAS 出处", "other_lang": "English",
        "footer_data": "氨基酸数据来源：USDA FoodData Central 与 FSANZ（按食物标注）。DIAAS 数值来自已发表文献，详见「参考文献」。",
        "nav_explainer": "什么是 DIAAS？", "nav_references": "参考文献", "nav_foods": "食物",
        "band": {"lower": "较低甲硫氨酸", "intermediate": "中等甲硫氨酸", "higher": "较高甲硫氨酸"},
        "na": "暂无",
        "ref_title": "参考文献与数据来源",
        "ref_intro": "本站的 DIAAS 值来自下列同行评议文献；所显示的氨基酸数值取自 USDA FoodData Central。「食物成分数据来源」下列出的各国家与地区食物成分数据库，是食物蛋白质与氨基酸组成的权威参考。现有整食物的 DIAAS 为整理自 Mathai 2017、Bailey 2020 与 FAO 2013 的代表值。",
        "explainer_title": "什么是 DIAAS？一份蛋白质量速读指南",
        "explainer_lead": "DIAAS 是衡量食物蛋白质满足人体氨基酸需求程度的现代标准。下面教你读懂本站的每一个数字。",
        "explainer": [
            {"h": "DIAAS 衡量什么", "p": [
                "DIAAS（可消化必需氨基酸评分）是 FAO 于 2013 年推荐的蛋白质量评价方法。它把一种蛋白提供的「可消化必需氨基酸」与人体需求量相比较，并采用每一种氨基酸在回肠（小肠末端）的真实消化率。",
                "评分 = 100 ×（所提供的可消化氨基酸 ÷ 所需氨基酸）的最小比值。取到这个最小比值的氨基酸，就是该食物的「第一限制性氨基酸」。"]},
            {"h": "怎么读这个分数", "p": [
                "FAO 定义三档：DIAAS ≥100 为优质蛋白，75–99 为高质量，低于 75 不作质量声明。与旧的 PDCAAS 不同，DIAAS 不封顶在 100，因此能把优质蛋白彼此区分开。"]},
            {"h": "限制性氨基酸", "p": [
                "一种蛋白的可用程度，取决于相对需求最稀缺的那个必需氨基酸。谷物通常受赖氨酸限制，豆类受含硫氨基酸（甲硫氨酸+半胱氨酸）限制。这正是为什么把互补的食物搭配在一起（如米饭配豆类）能提高混合物的蛋白质量。"]},
            {"h": "DIAAS 与 PDCAAS 的区别", "p": [
                "PDCAAS（1991）用整体蛋白的粪便消化率，且把分数截顶在 1.0。DIAAS 改用按单个氨基酸计的回肠消化率且不截顶，能更准确地描述优质蛋白（Mathai 2017）。"]},
            {"h": "关于本站的甲硫氨酸", "p": [
                "除 DIAAS 外，每种食物还标出每克蛋白质中的甲硫氨酸毫克数。甲硫氨酸属于含硫氨基酸，不同食物间含量相差数倍。「较低/中等/较高」标签只描述成分含量，不是健康评级。"]},
            {"h": "注意事项", "p": [
                "DIAAS 是针对特定食物与形态测得的，多来自猪或人的回肠实验；品种、烹饪、加工都会改变它。本站数值为代表值，并非每种做法的精确值。许多整食物——大多数蔬菜、蘑菇和香料——根本没有已发表的 DIAAS，本站标为「暂无已发表的值」，而非臆测填数。"]},
        ],
        "nav_research": "研究背景",
        "home_research_cta": "为什么是这几种氨基酸？查看研究背景 →",
        "ref_grp_quality": "蛋白质量（DIAAS）",
        "ref_grp_cancer": "癌症代谢研究中的氨基酸",
        "ref_grp_data": "食物成分数据来源",
        "research_title": "为什么是这几种氨基酸？癌症代谢研究中受关注的氨基酸",
        "research_lead": "本食物地图可按甲硫氨酸、半胱氨酸、甘氨酸、亮氨酸、支链氨基酸、精氨酸与赖氨酸筛选。这里说明科学家在研究癌细胞如何利用营养时，为什么会关注这几种氨基酸——以及同样重要的，这些研究并没有说什么。",
        "research_note": "本页整理的是已发表的实验室与动物研究，仅为背景信息，不构成医疗或饮食建议；本页不主张任何食物、氨基酸或饮食能预防、治疗或治愈癌症。这些研究大多为临床前研究（在细胞和小鼠中进行），能否、以及如何推及人体仍在研究中。如果您正在与癌症共处，请与您的肿瘤科团队和注册营养师一起做出饮食与治疗决定。",
        "research_sources": "背景取自 Lieu 等（2020）与 Gao 等（2019）。完整引用见：",
        "research": [
            {"h": "为什么癌症研究会关注氨基酸", "p": [
                "癌细胞分裂很快，要构建新细胞就需要持续供应氨基酸——它们既是蛋白质的组成单元，也是合成 DNA、抗氧化物和提供能量的原料。自奥托·瓦尔堡近一个世纪前的工作以来，研究者描绘了肿瘤如何重塑自身代谢，而氨基酸的处理正是经常被改变的通路之一（Lieu 等，2020）。",
                "因此，科学家会探究在实验室中限制某些氨基酸的供应能否减缓特定癌细胞。下面这几种，正是该领域讨论最多、且本站有成分数据的氨基酸。"]},
            {"h": "甲硫氨酸", "p": [
                "甲硫氨酸供给细胞主要的甲基供体循环，分裂中的细胞对其需求很高。在小鼠癌症模型中，限制膳食甲硫氨酸减缓了肿瘤生长，并改变了肿瘤对部分化疗与放疗的反应；同样的短期饮食也使一小群健康志愿者的一碳代谢指标发生了可测量的变化（Gao 等，2019）。",
                "这是在动物和短期人体代谢层面的早期研究，并不能证明低甲硫氨酸饮食可以治疗患者的癌症；而且甲硫氨酸是人体必需的氨基酸。"]},
            {"h": "半胱氨酸", "p": [
                "许多肿瘤细胞会摄取胱氨酸（半胱氨酸的二聚形式）来合成谷胱甘肽——一种保护它们免于「铁死亡」这类细胞死亡的抗氧化物。因此，限制半胱氨酸的可得性被作为一种在实验室中使某些癌细胞更脆弱的思路来研究（Lieu 等，2020）。"]},
            {"h": "甘氨酸与丝氨酸", "p": [
                "甘氨酸与丝氨酸提供细胞用于合成 DNA 和甲基基团的「一碳单元」。这种一碳代谢在快速分裂的癌症中经常被重塑，因而是研究的热点（Lieu 等，2020）。",
                "本站列出甘氨酸但未列丝氨酸，因为 USDA FoodData Central 对多数食物没有单独列出丝氨酸。"]},
            {"h": "亮氨酸与支链氨基酸（BCAA）", "p": [
                "亮氨酸、异亮氨酸和缬氨酸属于支链氨基酸。其中亮氨酸尤其有助于开启 mTORC1 通路——一个指挥细胞生长与合成蛋白质的核心信号。多种癌症中 BCAA 的代谢会发生改变，因此它既被作为生长信号、也被作为可能的干预靶点来研究（Lieu 等，2020）。"]},
            {"h": "精氨酸", "p": [
                "有些肿瘤丢失了让细胞自行合成精氨酸的酶（ASS1），只能从血液中获取精氨酸——这种依赖被称为「精氨酸营养缺陷」。研究者把它视为一个潜在弱点，并研究用消耗精氨酸的药物加以利用（Lieu 等，2020）。"]},
            {"h": "赖氨酸", "p": [
                "把赖氨酸列入这里出于一个不同而更简单的原因：它最常是限制谷物和许多植物性食物蛋白质量的氨基酸。按赖氨酸筛选有助于解释为什么有些植物蛋白的 DIAAS 较低——而这正是本站的主要用途。"]},
            {"h": "这与食物地图的关系", "p": [
                "首页的筛选器可让你按上述任一氨基酸（以每克蛋白质中的毫克数计）排序，并与最低 DIAAS 组合使用。这是一种探索食物成分的方式——例如，找出质量较高、同时甲硫氨酸较低的蛋白质。",
                "「较低／中等／较高」标签仅描述成分含量，并非健康评级；某种食物某种氨基酸「较低」或「较高」，本身并不说明它对任何人是好是坏。"]},
            {"h": "本页不是什么", "p": [
                "它不是饮食方案，不是癌症预防主张，也不是治疗建议。单一营养素在完整饮食与完整人体中的表现，与在一皿细胞中截然不同；在没有医疗监督的情况下限制必需氨基酸可能有害。请把本页当作理解数据的背景，涉及自身健康的任何问题，请咨询合格的专业人员。"]},
        ],
    },
}


LIMIT_EXPLAIN = {
    "SAA": {"en": "the sulfur amino acids (methionine and cysteine)", "zh": "含硫氨基酸（甲硫氨酸与半胱氨酸）"},
    "Lys": {"en": "lysine", "zh": "赖氨酸"},
    "Trp": {"en": "tryptophan", "zh": "色氨酸"},
}
BAND_ADJ = {"en": {"lower": "low", "intermediate": "moderate", "higher": "high"},
            "zh": {"lower": "较低", "intermediate": "中等", "higher": "较高"}}

# category guide / hub pages (target broader search queries + internal linking)
HUBS = [
    {"slug": "protein-quality-ranking",
     "title": {"en": "Protein quality ranking: foods scored by DIAAS",
               "zh": "蛋白质量排行：按 DIAAS 给食物打分排序"},
     "intro": {"en": "Every food on this site with a published DIAAS, ranked highest protein quality first. FAO tiers: DIAAS ≥100 is excellent, 75–99 high quality, below 75 carries no quality claim.",
               "zh": "本站所有有已发表 DIAAS 的食物，按蛋白质量从高到低排序。FAO 三档：DIAAS ≥100 为优质，75–99 为高质量，低于 75 不作质量声明。"},
     "filter": lambda f: f["diaas_val"] is not None,
     "sort": lambda f: -(f["diaas_val"] or 0)},
    {"slug": "complete-proteins",
     "title": {"en": "Complete proteins: foods with DIAAS 100 or higher",
               "zh": "完整蛋白：DIAAS ≥ 100 的食物"},
     "intro": {"en": "Foods whose protein scores DIAAS 100 or above — the FAO's “excellent quality” tier, meaning they meet adult essential amino-acid needs on their own.",
               "zh": "蛋白质 DIAAS ≥ 100 的食物——FAO「优质」档，单独食用即可满足成人必需氨基酸需求。"},
     "filter": lambda f: f["diaas_val"] is not None and f["diaas_val"] >= 100,
     "sort": lambda f: -(f["diaas_val"] or 0)},
    {"slug": "high-protein-plant-foods",
     "title": {"en": "High-protein plant foods", "zh": "高蛋白植物性食物"},
     "intro": {"en": "Plant foods ranked by protein per 100 g, with DIAAS and methionine for comparison.",
               "zh": "按每 100 克蛋白质含量排序的植物性食物，并列出 DIAAS 与甲硫氨酸便于比较。"},
     "filter": lambda f: f["category_en"].startswith("Plant"),
     "sort": lambda f: -(f["protein_val"] or 0), "limit": 20},
    {"slug": "best-plant-protein",
     "title": {"en": "Best plant proteins by quality (DIAAS) — complete plant proteins",
               "zh": "最优植物蛋白排行（按 DIAAS）— 完整植物蛋白"},
     "intro": {"en": "Plant foods with a published DIAAS, ranked by protein quality. Soy and a few pseudo-grains come closest to complete; most plant proteins are limited by lysine or the sulfur amino acids.",
               "zh": "有已发表 DIAAS 的植物性食物，按蛋白质量排序。大豆与少数假谷物最接近完整蛋白；多数植物蛋白受赖氨酸或含硫氨基酸限制。"},
     "filter": lambda f: f["category_en"].startswith("Plant") and f["diaas_val"] is not None,
     "sort": lambda f: -(f["diaas_val"] or 0)},
    {"slug": "diaas-of-legumes",
     "title": {"en": "DIAAS of legumes and beans", "zh": "豆类的 DIAAS"},
     "intro": {"en": "Protein quality (DIAAS) and limiting amino acids of beans, lentils, peas, and soy foods — most are limited by the sulfur amino acids.",
               "zh": "豆类、扁豆、豌豆与大豆制品的蛋白质量（DIAAS）与限制性氨基酸——多数受含硫氨基酸限制。"},
     "filter": lambda f: f["category_en"] == "Plant · legumes",
     "sort": lambda f: -(f["diaas_val"] or 0)},
    {"slug": "diaas-of-grains",
     "title": {"en": "DIAAS of grains and cereals", "zh": "谷物的 DIAAS"},
     "intro": {"en": "Protein quality of rice, wheat, oats, and other cereals — usually limited by lysine.",
               "zh": "大米、小麦、燕麦等谷物的蛋白质量——通常受赖氨酸限制。"},
     "filter": lambda f: f["category_en"] == "Plant · grains",
     "sort": lambda f: -(f["diaas_val"] or 0)},
    {"slug": "lower-methionine-foods",
     "title": {"en": "Lower-methionine foods (per gram of protein)", "zh": "较低甲硫氨酸的食物（每克蛋白）"},
     "intro": {"en": "Foods in the lower third for methionine per gram of protein. A neutral description of composition, not a health rating.",
               "zh": "每克蛋白质甲硫氨酸含量处于较低三分位的食物。仅为成分描述，非健康评级。"},
     "filter": lambda f: f["band"] == "lower",
     "sort": lambda f: (f["met_val"] or 0)},
]


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def quality_key(diaas):
    if diaas is None:
        return None
    if diaas >= 100:
        return "excellent"
    if diaas >= 75:
        return "high"
    return "noclaim"


def load_refs():
    refs = {}
    with REF_CSV.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            refs[r["key"]] = r
    return refs


def load_foods():
    amino = {}
    with AMINO_CSV.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            amino[r["slug"]] = r
    with DATA_CSV.open(encoding="utf-8") as fh:
        foods = list(csv.DictReader(fh))
    for f in foods:
        slug = f["slug"]
        # apply cited DIAAS overrides
        if slug in DIAAS_OVERRIDE:
            d, lim, src = DIAAS_OVERRIDE[slug]
            f["diaas"] = d
            if lim:
                f["diaas_limit"] = lim
            f["diaas_sources"] = src
        elif f.get("diaas"):
            f["diaas_sources"] = DEFAULT_DIAAS_SOURCES
        else:
            f["diaas_sources"] = []
        f["met_val"] = to_float(f.get("Met"))
        f["protein_val"] = to_float(f.get("protein_g_100g"))
        f["diaas_val"] = to_float(f.get("diaas"))
        f["quality"] = quality_key(f["diaas_val"])
        f["method_key"] = METHOD_FOR.get(slug, "default") if f.get("diaas") else None
        f["alt_diaas"] = ALT_DIAAS.get(slug)
        # full amino profile (mg/g protein) from amino_full.csv
        a = amino.get(slug, {})
        f["amino_full"] = {k: a.get(k, "") for k, *_ in FULL_AMINOS}
        # total of the full amino profile (mg/g protein) — drives the "All" view
        tot = sum(v for v in (to_float(a.get(k)) for k, *_ in FULL_AMINOS) if v is not None)
        f["aa_total"] = round(tot, 1) if tot else ""
        # serving size + protein per serving
        serv = SERVING_OVERRIDE.get(slug, CATEGORY_SERVING.get(f["category_en"], 100))
        f["serving_g"] = serv
        f["protein_per_serving"] = (
            round(f["protein_val"] * serv / 100, 1) if f["protein_val"] is not None else None
        )
    return foods


def assign_bands(foods):
    vals = sorted(f["met_val"] for f in foods if f["met_val"] is not None)
    n = len(vals)
    lo, hi = vals[n // 3], vals[(2 * n) // 3]
    for f in foods:
        m = f["met_val"]
        f["band"] = ("lower" if m < lo else "higher" if m >= hi else "intermediate") if m is not None else "intermediate"
    return lo, hi


def food_url(lang, slug):
    return f"{SITE_URL}/{lang}/foods/{slug}/"


def home_url(lang):
    return f"{SITE_URL}/{lang}/"


def page_url(lang, name):
    return f"{SITE_URL}/{lang}/{name}/"


def guides_index_url(lang):
    return f"{SITE_URL}/{lang}/guides/"


def guide_url(lang, slug):
    return f"{SITE_URL}/{lang}/guides/{slug}/"


QUALITY_SHORT = {"excellent": {"en": "excellent quality", "zh": "优质"},
                 "high": {"en": "high quality", "zh": "高质量"},
                 "noclaim": {"en": "no quality claim", "zh": "不作声明"}}
QUALITY_LONG = {
    "en": {"excellent": "which the FAO classes as an excellent-quality protein",
           "high": "which the FAO classes as a high-quality protein",
           "noclaim": "which is below the FAO threshold for a quality claim"},
    "zh": {"excellent": "达到 FAO「优质蛋白」标准", "high": "达到 FAO「高质量蛋白」标准",
           "noclaim": "低于 FAO 质量声明门槛"},
}


def make_description(food, lang):
    name = food["name_en"] if lang == "en" else food["name_zh"]
    lys = food["amino_full"].get("Lys")
    d = food.get("diaas")
    if lang == "en":
        s = f"{name} protein: "
        if d:
            s += f"DIAAS {d} ({QUALITY_SHORT[food['quality']]['en']}), "
        s += f"{food['protein_g_100g']} g protein/100g, methionine {food['Met']} mg/g"
        if lys:
            s += f", lysine {lys} mg/g"
        s += " protein. Full essential amino-acid profile."
    else:
        s = f"{name}蛋白质："
        if d:
            s += f"DIAAS {d}（{QUALITY_SHORT[food['quality']]['zh']}），"
        s += f"蛋白质 {food['protein_g_100g']} g/100g，每克蛋白甲硫氨酸 {food['Met']} mg"
        if lys:
            s += f"、赖氨酸 {lys} mg"
        s += "。完整必需氨基酸谱。"
    return s


def generate_blurb(food, lang):
    name = food["name_en"] if lang == "en" else food["name_zh"]
    p, d = food["protein_val"], food["diaas_val"]
    met, lys = food.get("Met"), food["amino_full"].get("Lys")
    adj = BAND_ADJ[lang][food["band"]]
    out = []
    if lang == "en":
        if p is not None:
            lvl = "a high-protein food" if p >= 20 else "a moderate-protein food" if p >= 10 else "a lower-protein food by weight"
            s = f"{name} provides {food['protein_g_100g']} g of protein per 100 g, making it {lvl}"
            if food["protein_per_serving"] is not None:
                s += f" — about {food['protein_per_serving']} g in a typical {food['serving_g']} g serving"
            out.append(s + ".")
        if d is not None:
            s = f"Its protein-quality score (DIAAS) is {food['diaas']}, {QUALITY_LONG['en'][food['quality']]}"
            le = LIMIT_EXPLAIN.get((food.get("diaas_limit") or "").strip(), {}).get("en")
            if le:
                s += f", and its first limiting amino acid is {le}"
            out.append(s + ".")
            if d >= 100:
                out.append("It supplies all essential amino acids in adequate amounts, so it counts as a complete protein on its own.")
        else:
            out.append(f"No DIAAS has been published for {name}, so its protein quality is not scored here; the full amino-acid profile is shown below.")
        if met:
            s = f"Measured per gram of protein, it is {adj} in methionine ({met} mg/g)"
            if lys:
                s += f" and provides {lys} mg/g of lysine"
            out.append(s + ".")
        return " ".join(out)
    else:
        if p is not None:
            lvl = "高蛋白食物" if p >= 20 else "中等蛋白食物" if p >= 10 else "按重量计蛋白较低的食物"
            s = f"{name}每 100 克提供 {food['protein_g_100g']} 克蛋白质，属于{lvl}"
            if food["protein_per_serving"] is not None:
                s += f"（每份约 {food['serving_g']} 克含 {food['protein_per_serving']} 克蛋白质）"
            out.append(s + "。")
        if d is not None:
            s = f"其蛋白质量评分（DIAAS）为 {food['diaas']}，{QUALITY_LONG['zh'][food['quality']]}"
            le = LIMIT_EXPLAIN.get((food.get("diaas_limit") or "").strip(), {}).get("zh")
            if le:
                s += f"，第一限制性氨基酸为{le}"
            out.append(s + "。")
            if d >= 100:
                out.append("它能以充足的量提供全部必需氨基酸，单独食用即为完整蛋白。")
        else:
            out.append(f"{name}尚无已发表的 DIAAS，本站不对其蛋白质量评分；下方列出完整氨基酸谱。")
        if met:
            s = f"以每克蛋白质计，其甲硫氨酸含量{adj}（{met} mg/g）"
            if lys:
                s += f"，赖氨酸 {lys} mg/g"
            out.append(s + "。")
        return "".join(out)


def related_foods(food, foods, n=6):
    same = [g for g in foods if g["category_en"] == food["category_en"] and g["slug"] != food["slug"]]
    same.sort(key=lambda g: abs((g["protein_val"] or 0) - (food["protein_val"] or 0)))
    return same[:n]


def breadcrumb_jsonld(items):
    return json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
                       "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u}
                                           for i, (n, u) in enumerate(items)]}, ensure_ascii=False)


def build():
    foods = load_foods()
    refs = load_refs()
    lo, hi = assign_bands(foods)
    print(f"Methionine tertiles (mg/g protein): lower < {lo:.1f} <= intermediate < {hi:.1f} <= higher")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True, lstrip_blocks=True,
    )

    client_foods = [
        {"slug": f["slug"], "name_en": f["name_en"], "name_zh": f["name_zh"],
         "cat_en": f["category_en"], "cat_zh": f["category_zh"],
         "group": f["category_en"].split(" ")[0], "band": f["band"],
         "protein": f["protein_val"], "met": f["met_val"], "diaas": f["diaas_val"],
         "amino": {k: to_float(f["amino_full"].get(k)) for k, *_ in FULL_AMINOS}}
        for f in foods
    ]
    categories = sorted({(f["category_en"], f["category_zh"]) for f in foods})

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(STATIC, OUT / "static")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    base_ctx = {"SITE_URL": SITE_URL, "LANGS": LANGS, "HTML_LANG": HTML_LANG, "DISCLAIMER": DISCLAIMER}

    index_tpl = env.get_template("index.html")
    food_tpl = env.get_template("food.html")
    root_tpl = env.get_template("root.html")
    explainer_tpl = env.get_template("explainer.html")
    research_tpl = env.get_template("research.html")
    refs_tpl = env.get_template("references.html")

    def nav_urls(lang):
        return {"foods": home_url(lang), "guides": guides_index_url(lang),
                "explainer": page_url(lang, "what-is-diaas"),
                "research": page_url(lang, "amino-acids-and-cancer-research"),
                "references": page_url(lang, "references")}

    # homepages
    dvals = [f["diaas_val"] for f in foods if f["diaas_val"]]
    diaas_max = int(((max(dvals) // 5) + 1) * 5) if dvals else 120
    for lang in LANGS:
        s = STR[lang]
        ordered = sorted(foods, key=lambda f: f["name_en"].lower())
        amino_opts = [{"key": k, "label": (en if lang == "en" else zh)} for k, en, zh in AMINO_FILTER]
        html = index_tpl.render(
            **base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s, foods=ordered,
            categories=categories, amino_filter=AMINO_FILTER, amino_cols=AMINO_COLS,
            abbrevs=ABBREVS, nav=nav_urls(lang),
            amino_topics=[{"url": page_url(lang, "amino/" + t["slug"]),
                           "name": t["name_en"] if lang == "en" else t["name_zh"]}
                          for t in AMINO_TOPICS],
            canonical=home_url(lang), alt_urls={l: home_url(l) for l in LANGS},
            client_data=json.dumps(client_foods, ensure_ascii=False),
            ui_json=json.dumps({"lang": lang, "band": s["band"], "compareMax": 4,
                                "scatterX": s["th_met"], "scatterY": s["th_diaas"],
                                "na": s["na"], "diaas": s["th_diaas"], "protein": s["th_protein"],
                                "aminoOptions": amino_opts, "diaasMax": diaas_max,
                                "unit": ("mg/g protein" if lang == "en" else "mg/g 蛋白"),
                                "colUnit": ("(mg/g protein)" if lang == "en" else "(mg/g 蛋白)"),
                                "maxLabel": ("Max" if lang == "en" else "最高"),
                                "minDiaasLabel": ("Min DIAAS" if lang == "en" else "DIAAS 最低"),
                                "presetLabel": ("High DIAAS · low" if lang == "en" else "高 DIAAS · 低"),
                                "groupLabels": {"Animal": s["grp_animal"], "Plant": s["grp_plant"],
                                                "Spice": s["grp_spice"], "Special": s["grp_special"]}},
                               ensure_ascii=False),
        )
        out = OUT / lang / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

    # food pages
    for lang in LANGS:
        s = STR[lang]
        for f in foods:
            name = f["name_en"] if lang == "en" else f["name_zh"]
            alt_name = f["name_zh"] if lang == "en" else f["name_en"]
            cat = f["category_en"] if lang == "en" else f["category_zh"]
            limit = f.get("diaas_limit", "").strip()
            limit_label = LIMIT_LABEL.get(limit, {}).get(lang, "") if (limit and limit != "NA") else ""
            amino_rows = [{"label": (en if lang == "en" else zh), "value": f["amino_full"].get(k, ""),
                           "essential": ess} for k, en, zh, ess in FULL_AMINOS]
            quality_label = QUALITY[f["quality"]][lang] if f["quality"] else ""
            src_list = [{"key": k, "label": refs[k]["ref_en" if lang == "en" else "ref_zh"],
                         "url": refs[k]["url"]} for k in f["diaas_sources"] if k in refs]
            blurb = generate_blurb(f, lang)
            rel = [{"name": (g["name_en"] if lang == "en" else g["name_zh"]),
                    "url": food_url(lang, g["slug"])} for g in related_foods(f, foods)]
            crumbs = breadcrumb_jsonld([(s["bc_home"], home_url(lang)),
                                        (s["nav_foods"], home_url(lang)),
                                        (name, food_url(lang, f["slug"]))])
            method_label = DIAAS_METHOD[lang][f["method_key"]] if f["method_key"] else ""
            alt = None
            if f["alt_diaas"]:
                av, al, asrc = f["alt_diaas"]
                alt = {"val": av,
                       "limit": LIMIT_LABEL.get(al, {}).get(lang, al),
                       "method": ALT_METHOD[lang],
                       "source": refs.get(asrc, {}).get("ref_en" if lang == "en" else "ref_zh", ""),
                       "url": refs.get(asrc, {}).get("url", "")}
            jsonld = {
                "@context": "https://schema.org", "@type": "Dataset",
                "name": f"{name} — {s['site_name']}", "description": make_description(f, lang),
                "url": food_url(lang, f["slug"]), "inLanguage": HTML_LANG[lang],
                "isAccessibleForFree": True,
                "keywords": ["methionine", "DIAAS", "protein quality", "amino acids", name, alt_name],
                "creator": {"@type": "Organization", "name": s["site_name"]},
                "variableMeasured": (
                    [{"@type": "PropertyValue", "name": en, "value": f["amino_full"].get(k),
                      "unitText": "mg/g protein"} for k, en, zh, ess in FULL_AMINOS if f["amino_full"].get(k)]
                    + ([{"@type": "PropertyValue", "name": "DIAAS", "value": f.get("diaas")}] if f.get("diaas") else [])
                    + [{"@type": "PropertyValue", "name": "Protein", "value": f.get("protein_g_100g"), "unitText": "g/100g"}]
                ),
            }
            html = food_tpl.render(
                **base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s, food=f, name=name,
                alt_name=alt_name, category=cat, band_label=s["band"][f["band"]],
                source_label=SOURCE_LABEL[lang].get(f.get("source") or "USDA", SOURCE_LABEL[lang]["USDA"]),
                amino_rows=amino_rows, limit_label=limit_label, quality_label=quality_label,
                diaas_sources=src_list, method_label=method_label, alt=alt,
                blurb=blurb, related=rel, breadcrumb=crumbs,
                nav=nav_urls(lang), description=make_description(f, lang),
                canonical=food_url(lang, f["slug"]),
                alt_urls={l: food_url(l, f["slug"]) for l in LANGS},
                jsonld=json.dumps(jsonld, ensure_ascii=False, indent=2),
            )
            out = OUT / lang / "foods" / f["slug"] / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")

    # explainer + research + references pages
    ref_group_keys = [
        ("ref_grp_quality", ["mathai2017", "bailey2020", "herreman2020", "nosworthy2017",
                             "han2019", "hammer2023", "fao2013"]),
        ("ref_grp_cancer", ["lieu2020", "gao2019"]),
        ("ref_grp_data", ["usda", "china_cdc", "hk_cfs", "fsanz", "thai_fcd"]),
    ]
    for lang in LANGS:
        s = STR[lang]
        lang_key = "ref_en" if lang == "en" else "ref_zh"
        (OUT / lang / "what-is-diaas").mkdir(parents=True, exist_ok=True)
        (OUT / lang / "what-is-diaas" / "index.html").write_text(
            explainer_tpl.render(**base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s,
                                 nav=nav_urls(lang), canonical=page_url(lang, "what-is-diaas"),
                                 alt_urls={l: page_url(l, "what-is-diaas") for l in LANGS}),
            encoding="utf-8")
        (OUT / lang / "amino-acids-and-cancer-research").mkdir(parents=True, exist_ok=True)
        (OUT / lang / "amino-acids-and-cancer-research" / "index.html").write_text(
            research_tpl.render(**base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s,
                                nav=nav_urls(lang),
                                canonical=page_url(lang, "amino-acids-and-cancer-research"),
                                alt_urls={l: page_url(l, "amino-acids-and-cancer-research") for l in LANGS}),
            encoding="utf-8")
        ref_groups = [{"heading": s[hk], "refs": [refs[k] for k in keys if k in refs]}
                      for hk, keys in ref_group_keys]
        (OUT / lang / "references").mkdir(parents=True, exist_ok=True)
        (OUT / lang / "references" / "index.html").write_text(
            refs_tpl.render(**base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s, nav=nav_urls(lang),
                            ref_groups=ref_groups, lang_key=lang_key,
                            canonical=page_url(lang, "references"),
                            alt_urls={l: page_url(l, "references") for l in LANGS}),
            encoding="utf-8")

    # single-amino-acid topic pages (long-tail SEO)
    amino_tpl = env.get_template("amino.html")
    for topic in AMINO_TOPICS:
        key = topic["key"]
        ranked = [f for f in foods if to_float(topic_raw(f, key)) is not None]
        ranked.sort(key=lambda f: to_float(topic_raw(f, key)), reverse=True)
        vals = sorted(to_float(topic_raw(f, key)) for f in ranked)
        n = len(vals)
        for lang in LANGS:
            s = STR[lang]
            name = topic["name_en"] if lang == "en" else topic["name_zh"]
            rows = []
            for f in ranked:
                v = to_float(topic_raw(f, key))
                idx = sum(1 for x in vals if x < v)
                t = idx / (n - 1) if n > 1 else 0.5
                rows.append({
                    "name": f["name_en"] if lang == "en" else f["name_zh"],
                    "url": food_url(lang, f["slug"]),
                    "cat": (f["category_en"] if lang == "en" else f["category_zh"]).split("·")[0].strip(),
                    "value": topic_raw(f, key), "color": heat_color(t),
                    "protein": f.get("protein_g_100g") or s["na"],
                    "diaas": f.get("diaas") or s["na"],
                })
            if lang == "en":
                title = f"Foods high in {name} — {name} per gram of protein (112 foods)"
                h1 = f"{name} content of foods"
                desc = (f"{name} content of 112 common animal and plant foods, ranked per "
                        f"gram of protein, with DIAAS protein-quality scores. Data from USDA and FSANZ.")
            else:
                title = f"富含{name}的食物 — 每克蛋白{name}含量（112 种食物）"
                h1 = f"食物中的{name}含量"
                desc = (f"112 种常见动物与植物性食物的{name}含量（每克蛋白）排行，"
                        f"附 DIAAS 蛋白质量评分。数据来自 USDA 与 FSANZ。")
            out = OUT / lang / "amino" / topic["slug"]
            out.mkdir(parents=True, exist_ok=True)
            (out / "index.html").write_text(
                amino_tpl.render(**base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s,
                                 nav=nav_urls(lang), canonical=page_url(lang, f"amino/{topic['slug']}"),
                                 alt_urls={l: page_url(l, f"amino/{topic['slug']}") for l in LANGS},
                                 title=title, h1=h1, description=desc, blurb=topic["blurb_en"] if lang == "en" else topic["blurb_zh"],
                                 code=topic["code"], rows=rows),
                encoding="utf-8")

    # guide / hub pages + guides index
    hub_tpl = env.get_template("hub.html")
    guides_tpl = env.get_template("guides_index.html")
    for lang in LANGS:
        s = STR[lang]
        name_key = "name_en" if lang == "en" else "name_zh"
        cat_key = "category_en" if lang == "en" else "category_zh"
        hub_links = []
        for h in HUBS:
            items = [f for f in foods if h["filter"](f)]
            if "sort" in h:
                items = sorted(items, key=h["sort"])
            if "limit" in h:
                items = items[:h["limit"]]
            crumbs = breadcrumb_jsonld([(s["bc_home"], home_url(lang)),
                                        (s["bc_guides"], guides_index_url(lang)),
                                        (h["title"][lang], guide_url(lang, h["slug"]))])
            html = hub_tpl.render(
                **base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s, nav=nav_urls(lang),
                title=h["title"][lang], intro=h["intro"][lang], foods=items,
                name_key=name_key, cat_key=cat_key, food_base=f"{SITE_URL}/{lang}/foods/",
                quality_labels={k: QUALITY_SHORT[k][lang] for k in QUALITY_SHORT},
                breadcrumb=crumbs, canonical=guide_url(lang, h["slug"]),
                alt_urls={l: guide_url(l, h["slug"]) for l in LANGS})
            out = OUT / lang / "guides" / h["slug"] / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            hub_links.append({"title": h["title"][lang], "intro": h["intro"][lang],
                              "url": guide_url(lang, h["slug"]), "count": len(items)})
        out = OUT / lang / "guides" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(guides_tpl.render(
            **base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s, nav=nav_urls(lang),
            hubs=hub_links, canonical=guides_index_url(lang),
            alt_urls={l: guides_index_url(l) for l in LANGS}), encoding="utf-8")

    (OUT / "index.html").write_text(
        root_tpl.render(**base_ctx, alt_urls={l: home_url(l) for l in LANGS}), encoding="utf-8")
    (OUT / "404.html").write_text(
        env.get_template("notfound.html").render(**base_ctx), encoding="utf-8")

    write_sitemap(foods)
    write_robots()
    n = 1 + len(LANGS) * (1 + 3 + 1 + len(HUBS) + len(foods))
    print(f"Built {n} HTML pages ({len(foods)} foods, {len(HUBS)} guides, +explainer +references) -> {OUT}")
    print(f"SITE_URL = {SITE_URL}")


def write_sitemap(foods):
    XN = "http://www.w3.org/1999/xhtml"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="{XN}">']

    def entry(urls_by_lang):
        for lang, loc in urls_by_lang.items():
            lines.append("  <url>")
            lines.append(f"    <loc>{loc}</loc>")
            for l, u in urls_by_lang.items():
                lines.append(f'    <xhtml:link rel="alternate" hreflang="{HTML_LANG[l]}" href="{u}"/>')
            lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{urls_by_lang["en"]}"/>')
            lines.append("  </url>")

    entry({l: home_url(l) for l in LANGS})
    entry({l: page_url(l, "what-is-diaas") for l in LANGS})
    entry({l: page_url(l, "amino-acids-and-cancer-research") for l in LANGS})
    entry({l: page_url(l, "references") for l in LANGS})
    entry({l: guides_index_url(l) for l in LANGS})
    for h in HUBS:
        entry({l: guide_url(l, h["slug"]) for l in LANGS})
    for t in AMINO_TOPICS:
        entry({l: page_url(l, "amino/" + t["slug"]) for l in LANGS})
    for f in foods:
        entry({l: food_url(l, f["slug"]) for l in LANGS})
    lines.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_robots():
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")


if __name__ == "__main__":
    build()
