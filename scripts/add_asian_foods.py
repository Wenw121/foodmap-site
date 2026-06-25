#!/usr/bin/env python3
"""
Fetch full amino-acid profiles for a curated set of Asian staple foods from
USDA FoodData Central and STAGE candidate rows for data/foods.csv and
data/amino_full.csv (written to /tmp for review, not appended automatically).

Reuses the same matching approach as fetch_amino.py. Values are mg per gram of
protein. Run, eyeball the printed table, then append the staged rows.
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FDC_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_FOOD = "https://api.nal.usda.gov/fdc/v1/food/"
PROTEIN = "203"
AA_NUM = {"Trp": "501", "Thr": "502", "Ile": "503", "Leu": "504", "Lys": "505",
          "Met": "506", "Cys": "507", "Phe": "508", "Tyr": "509", "Val": "510",
          "Arg": "511", "His": "512", "Gly": "516"}
FULL_COLS = ["Trp", "Thr", "Ile", "Leu", "Lys", "Met", "Cys", "Phe", "Tyr",
             "Val", "His", "Arg", "Gly"]

# slug, name_en, name_zh, category_en, category_zh, USDA query
NEW = [
    ("nori-laver", "Nori (laver)", "紫菜", "Plant · vegetables/algae", "植物 · 蔬菜/藻类", "Seaweed, laver, raw"),
    ("wakame", "Wakame seaweed", "裙带菜", "Plant · vegetables/algae", "植物 · 蔬菜/藻类", "Seaweed, wakame, raw"),
    ("kelp-kombu", "Kelp (kombu)", "海带", "Plant · vegetables/algae", "植物 · 蔬菜/藻类", "Seaweed, kelp, raw"),
    ("adzuki-beans", "Adzuki beans", "红豆", "Plant · legumes", "植物 · 豆类", "Adzuki beans, mature seeds, cooked, boiled, without salt"),
    ("mung-bean-sprouts", "Mung bean sprouts", "绿豆芽", "Plant · vegetables/algae", "植物 · 蔬菜/藻类", "Mung beans, mature seeds, sprouted, raw"),
    ("soy-milk", "Soy milk", "豆浆", "Plant · legumes", "植物 · 豆类", "Soymilk, original and vanilla, unfortified"),
    ("seitan-wheat-gluten", "Seitan (wheat gluten)", "面筋", "Plant · grains", "植物 · 谷物", "Vital wheat gluten"),
    ("bok-choy", "Bok choy (pak choi)", "青江菜", "Plant · vegetables/algae", "植物 · 蔬菜/藻类", "Cabbage, chinese (pak-choi), raw"),
    ("eel", "Eel (unagi)", "鳗鱼", "Animal · fish/seafood", "动物 · 鱼/海鲜", "Fish, eel, mixed species, raw"),
]


def load_key():
    key = os.environ.get("USDA_API_KEY")
    if not key:
        envf = ROOT / ".env"
        if envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("USDA_API_KEY="):
                    key = line.split("=", 1)[1].strip()
    return key or "DEMO_KEY"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "FoodMap/2.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


# foods where token-matching is unreliable -> pin the exact USDA fdcId
FORCE_ID = {"seitan-wheat-gluten": 168147, "bok-choy": 170390}


def fetch_by_id(fid, key):
    detail = get(f"{FDC_FOOD}{fid}?api_key={key}")
    nums = {str(n.get("nutrient", {}).get("number", "")): n.get("amount")
            for n in detail.get("foodNutrients", [])}
    return fid, detail["description"], nums


def find_entry(query, key):
    qs = urllib.parse.urlencode({"api_key": key, "query": query,
                                 "dataType": "SR Legacy,Foundation", "pageSize": 25})
    hits = get(f"{FDC_SEARCH}?{qs}").get("foods", [])
    if not hits:
        return None, None, None
    target = query.strip().lower()

    def score(h):
        desc = h.get("description", "").strip().lower()
        if desc == target:
            return 1000
        toks = target.replace(",", " ").split()
        return sum(1 for t in toks if t in desc)

    for hit in sorted(hits, key=score, reverse=True)[:5]:
        detail = get(f"{FDC_FOOD}{hit['fdcId']}?api_key={key}")
        nums = {str(n.get("nutrient", {}).get("number", "")): n.get("amount")
                for n in detail.get("foodNutrients", [])}
        if nums.get(PROTEIN) and nums.get(AA_NUM["Met"]):
            return hit["fdcId"], detail["description"], nums
        time.sleep(0.2)
    return None, None, None


def mgg(nums, col, protein):
    amt = nums.get(AA_NUM[col])
    return round(amt * 1000 / protein, 1) if (amt and protein) else None


def main():
    key = load_key()
    print(f"key {key[:6]}… ({'real' if key != 'DEMO_KEY' else 'DEMO'})\n", file=sys.stderr)
    foods_rows, amino_rows = [], []
    for slug, en, zh, cat_en, cat_zh, q in NEW:
        try:
            if slug in FORCE_ID:
                fid, desc, nums = fetch_by_id(FORCE_ID[slug], key)
            else:
                fid, desc, nums = find_entry(q, key)
        except Exception as e:
            print(f"[ERR] {en}: {e}", file=sys.stderr)
            continue
        if not nums:
            print(f"[MISS] {en}  (query: {q})", file=sys.stderr)
            continue
        protein = nums.get(PROTEIN)
        full = {c: mgg(nums, c, protein) for c in FULL_COLS}
        leu, ile, val = full["Leu"], full["Ile"], full["Val"]
        bcaa = round((leu or 0) + (ile or 0) + (val or 0), 1) if all(x is not None for x in (leu, ile, val)) else ""
        foods_rows.append([slug, en, zh, cat_en, cat_zh, protein,
                           full["Met"] or "", full["Cys"] or "", full["Leu"] or "",
                           bcaa, full["Arg"] or "", full["Gly"] or "", full["Trp"] or "",
                           "", "", desc])
        amino_rows.append([slug, en, desc, "added"] + [full[c] if full[c] is not None else "" for c in FULL_COLS])
        print(f"{en:<22} -> {desc[:44]:<44} prot={protein:<5} Met={full['Met']} Lys={full['Lys']} Leu={full['Leu']} BCAA={bcaa}", file=sys.stderr)

    with open("/tmp/new_foods.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(foods_rows)
    with open("/tmp/new_amino.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(amino_rows)
    print(f"\nStaged {len(foods_rows)} foods -> /tmp/new_foods.csv + /tmp/new_amino.csv", file=sys.stderr)


if __name__ == "__main__":
    main()
