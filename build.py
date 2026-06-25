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
    "spirulina-dried": 7,
}

# full amino-acid display order: (key, en, zh, is_essential)
FULL_AMINOS = [
    ("His", "Histidine (His)", "组氨酸 (His)", True),
    ("Ile", "Isoleucine (Ile)", "异亮氨酸 (Ile)", True),
    ("Leu", "Leucine (Leu)", "亮氨酸 (Leu)", True),
    ("Lys", "Lysine (Lys)", "赖氨酸 (Lys)", True),
    ("Met", "Methionine (Met)", "甲硫氨酸 (Met)", True),
    ("Cys", "Cysteine (Cys)", "半胱氨酸 (Cys)", False),
    ("Phe", "Phenylalanine (Phe)", "苯丙氨酸 (Phe)", True),
    ("Tyr", "Tyrosine (Tyr)", "酪氨酸 (Tyr)", False),
    ("Thr", "Threonine (Thr)", "苏氨酸 (Thr)", True),
    ("Trp", "Tryptophan (Trp)", "色氨酸 (Trp)", True),
    ("Val", "Valine (Val)", "缬氨酸 (Val)", True),
    ("Arg", "Arginine (Arg)", "精氨酸 (Arg)", False),
    ("Gly", "Glycine (Gly)", "甘氨酸 (Gly)", False),
]

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
        "site_name": "Methionine Food Map",
        "tagline": "Protein quality (DIAAS) and full amino-acid profiles of 85 common foods.",
        "intro": (
            "An interactive, bilingual reference for the methionine content, full "
            "essential amino-acid profile, and protein quality (DIAAS) of 85 common "
            "animal and plant foods. Search, filter by category, compare foods side "
            "by side, and explore the methionine-vs-DIAAS map. Amino-acid values are "
            "milligrams per gram of protein, from USDA FoodData Central."
        ),
        "search_ph": "Search a food (e.g. salmon, tofu)…",
        "all_categories": "All categories", "all_bands": "All methionine levels",
        "th_food": "Food", "th_category": "Category", "th_band": "Methionine",
        "th_protein": "Protein (g/100g)", "th_met": "Methionine (mg/g protein)",
        "th_diaas": "DIAAS", "th_compare": "Compare",
        "compare_title": "Comparison",
        "compare_hint": "Select up to 4 foods in the table to compare them here.",
        "compare_clear": "Clear", "scatter_title": "Methionine vs DIAAS",
        "scatter_hint": "Each point is a food. X = methionine (mg/g protein), Y = DIAAS. Hover for the name; click to open its page.",
        "no_results": "No foods match your filters.", "view": "View",
        "back_home": "← All foods", "amino_profile": "Full amino-acid profile",
        "th_value": "mg/g protein", "essential": "Essential",
        "diaas_section": "Protein quality (DIAAS)", "diaas_na": "No published DIAAS value",
        "diaas_na_note": "DIAAS requires ileal digestibility studies that have not been published for this food.",
        "limiting_aa": "First limiting amino acid", "quality_cat": "FAO quality category",
        "diaas_method_label": "Method", "also_measured": "Also measured",
        "fdc_source": "USDA FoodData Central match", "band_label": "Methionine (mg/g protein)",
        "protein_label": "Protein content", "per_serving": "Protein per serving",
        "serving_note": "≈ per typical serving",
        "diaas_source": "DIAAS source", "other_lang": "中文",
        "footer_data": "Amino-acid data: USDA FoodData Central. DIAAS values from published literature — see References.",
        "nav_explainer": "What is DIAAS?", "nav_references": "References", "nav_foods": "Foods",
        "band": {"lower": "Lower methionine", "intermediate": "Intermediate methionine", "higher": "Higher methionine"},
        "na": "N/A",
        "ref_title": "References & data sources",
        "ref_intro": "All DIAAS values on this site come from the peer-reviewed literature below; amino-acid composition is from USDA FoodData Central. Existing whole-food DIAAS values are representative figures compiled from Mathai 2017, Bailey 2020, and FAO 2013.",
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
    },
    "zh": {
        "site_name": "甲硫氨酸食物地图",
        "tagline": "85 种常见食物的蛋白质量（DIAAS）与完整氨基酸谱。",
        "intro": (
            "一个交互式双语参考工具，收录 85 种常见动物与植物性食物的甲硫氨酸含量、"
            "完整必需氨基酸谱与蛋白质量（DIAAS）。可搜索、按分类筛选、并排对比，"
            "并探索「甲硫氨酸—DIAAS」分布图。氨基酸数值为每克蛋白质中的毫克数，"
            "来源于 USDA FoodData Central。"
        ),
        "search_ph": "搜索食物（如 三文鱼、豆腐）…",
        "all_categories": "全部分类", "all_bands": "全部甲硫氨酸水平",
        "th_food": "食物", "th_category": "分类", "th_band": "甲硫氨酸",
        "th_protein": "蛋白质 (g/100g)", "th_met": "甲硫氨酸 (mg/g 蛋白)",
        "th_diaas": "DIAAS", "th_compare": "对比",
        "compare_title": "对比", "compare_hint": "在表格中最多勾选 4 种食物，在此并排对比。",
        "compare_clear": "清除", "scatter_title": "甲硫氨酸 vs DIAAS",
        "scatter_hint": "每个点代表一种食物。X = 甲硫氨酸（mg/g 蛋白），Y = DIAAS。悬停看名称，点击进入详情页。",
        "no_results": "没有符合筛选条件的食物。", "view": "查看",
        "back_home": "← 全部食物", "amino_profile": "完整氨基酸谱",
        "th_value": "mg/g 蛋白", "essential": "必需",
        "diaas_section": "蛋白质量（DIAAS）", "diaas_na": "暂无已发表的 DIAAS 值",
        "diaas_na_note": "DIAAS 需要回肠消化率实验数据，该食物尚无已发表研究。",
        "limiting_aa": "第一限制性氨基酸", "quality_cat": "FAO 质量等级",
        "diaas_method_label": "测定方法", "also_measured": "另有实测值",
        "fdc_source": "USDA FoodData Central 匹配项", "band_label": "甲硫氨酸 (mg/g 蛋白)",
        "protein_label": "蛋白质含量", "per_serving": "每份蛋白质",
        "serving_note": "≈ 每份常见食用量",
        "diaas_source": "DIAAS 出处", "other_lang": "English",
        "footer_data": "氨基酸数据来源：USDA FoodData Central。DIAAS 数值来自已发表文献，详见「参考文献」。",
        "nav_explainer": "什么是 DIAAS？", "nav_references": "参考文献", "nav_foods": "食物",
        "band": {"lower": "较低甲硫氨酸", "intermediate": "中等甲硫氨酸", "higher": "较高甲硫氨酸"},
        "na": "暂无",
        "ref_title": "参考文献与数据来源",
        "ref_intro": "本站所有 DIAAS 值均来自下列同行评议文献；氨基酸组成来自 USDA FoodData Central。现有整食物的 DIAAS 为整理自 Mathai 2017、Bailey 2020 与 FAO 2013 的代表值。",
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
    },
}


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


def make_description(food, lang):
    name = food["name_en"] if lang == "en" else food["name_zh"]
    band = STR[lang]["band"][food["band"]]
    diaas = food.get("diaas")
    if lang == "en":
        d = f"{name}: {band.lower()}, {food['Met']} mg methionine per gram of protein"
        if diaas:
            d += f", DIAAS {diaas}"
        d += f". Protein {food['protein_g_100g']} g/100g. Full essential amino-acid profile and protein quality."
    else:
        d = f"{name}：{band}，每克蛋白质含甲硫氨酸 {food['Met']} mg"
        if diaas:
            d += f"，DIAAS {diaas}"
        d += f"。蛋白质 {food['protein_g_100g']} g/100g。完整必需氨基酸谱与蛋白质量。"
    return d


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
    refs_tpl = env.get_template("references.html")

    def nav_urls(lang):
        return {"foods": home_url(lang), "explainer": page_url(lang, "what-is-diaas"),
                "references": page_url(lang, "references")}

    # homepages
    for lang in LANGS:
        s = STR[lang]
        ordered = sorted(foods, key=lambda f: f["name_en"].lower())
        html = index_tpl.render(
            **base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s, foods=ordered,
            categories=categories, nav=nav_urls(lang), canonical=home_url(lang),
            alt_urls={l: home_url(l) for l in LANGS},
            client_data=json.dumps(client_foods, ensure_ascii=False),
            ui_json=json.dumps({"lang": lang, "band": s["band"], "compareMax": 4,
                                "scatterX": s["th_met"], "scatterY": s["th_diaas"],
                                "na": s["na"], "diaas": s["th_diaas"], "protein": s["th_protein"]},
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
                amino_rows=amino_rows, limit_label=limit_label, quality_label=quality_label,
                diaas_sources=src_list, method_label=method_label, alt=alt,
                nav=nav_urls(lang), description=make_description(f, lang),
                canonical=food_url(lang, f["slug"]),
                alt_urls={l: food_url(l, f["slug"]) for l in LANGS},
                jsonld=json.dumps(jsonld, ensure_ascii=False, indent=2),
            )
            out = OUT / lang / "foods" / f["slug"] / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")

    # explainer + references pages
    for lang in LANGS:
        s = STR[lang]
        (OUT / lang / "what-is-diaas").mkdir(parents=True, exist_ok=True)
        (OUT / lang / "what-is-diaas" / "index.html").write_text(
            explainer_tpl.render(**base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s,
                                 nav=nav_urls(lang), canonical=page_url(lang, "what-is-diaas"),
                                 alt_urls={l: page_url(l, "what-is-diaas") for l in LANGS}),
            encoding="utf-8")
        ref_rows = [refs[k] for k in ["mathai2017", "bailey2020", "herreman2020", "nosworthy2017",
                                       "han2019", "hammer2023", "fao2013", "usda"] if k in refs]
        (OUT / lang / "references").mkdir(parents=True, exist_ok=True)
        (OUT / lang / "references" / "index.html").write_text(
            refs_tpl.render(**base_ctx, lang=lang, html_lang=HTML_LANG[lang], s=s, nav=nav_urls(lang),
                            refs=ref_rows, lang_key=("ref_en" if lang == "en" else "ref_zh"),
                            canonical=page_url(lang, "references"),
                            alt_urls={l: page_url(l, "references") for l in LANGS}),
            encoding="utf-8")

    (OUT / "index.html").write_text(
        root_tpl.render(**base_ctx, alt_urls={l: home_url(l) for l in LANGS}), encoding="utf-8")

    write_sitemap(foods)
    write_robots()
    n = 1 + len(LANGS) * (1 + 2 + len(foods))
    print(f"Built {n} HTML pages ({len(foods)} foods, +explainer +references) -> {OUT}")
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
    entry({l: page_url(l, "references") for l in LANGS})
    for f in foods:
        entry({l: food_url(l, f["slug"]) for l in LANGS})
    lines.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_robots():
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")


if __name__ == "__main__":
    build()
