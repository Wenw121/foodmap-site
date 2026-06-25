#!/usr/bin/env python3
"""
Fetch the FULL essential-amino-acid profile for every food in data/foods.csv
from USDA FoodData Central, normalized to mg per gram of protein.

Matches each food by its existing `fdc_match` description (the real USDA
description already stored), so we re-read the SAME FDC entries the dataset was
built from — then pull the amino acids that weren't kept the first time
(Lys, His, Thr, Ile, Val, Phe, Tyr) alongside the existing seven.

Output: data/amino_full.csv  (slug + all amino acids, mg/g protein)

Usage:
    USDA_API_KEY=xxxx python scripts/fetch_amino.py
    # or it reads .env (USDA_API_KEY=...) automatically
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data" / "foods.csv"
OUT = ROOT / "data" / "amino_full.csv"

FDC_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_FOOD = "https://api.nal.usda.gov/fdc/v1/food/"

PROTEIN = "203"
# nutrient number -> our column name (9 essential AAs + Arg, Gly, Cys, Tyr)
AA_NUM = {
    "Trp": "501", "Thr": "502", "Ile": "503", "Leu": "504", "Lys": "505",
    "Met": "506", "Cys": "507", "Phe": "508", "Tyr": "509", "Val": "510",
    "Arg": "511", "His": "512", "Gly": "516",
}
COLS = ["Trp", "Thr", "Ile", "Leu", "Lys", "Met", "Cys", "Phe", "Tyr",
        "Val", "His", "Arg", "Gly"]


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


def find_entry(fdc_match, name_en, key):
    """Return (description, nutrient_number->amount) for the best USDA match."""
    query = fdc_match or name_en
    qs = urllib.parse.urlencode({
        "api_key": key, "query": query,
        "dataType": "SR Legacy,Foundation", "pageSize": 25,
    })
    hits = get(f"{FDC_SEARCH}?{qs}").get("foods", [])
    if not hits:
        return None, None
    target = (fdc_match or "").strip().lower()

    def score(h):
        desc = h.get("description", "").strip().lower()
        if target and desc == target:
            return 1000  # exact description match
        toks = [t for t in target.replace(",", " ").split()]
        return sum(1 for t in toks if t in desc)

    ranked = sorted(hits, key=score, reverse=True)
    for hit in ranked[:5]:
        detail = get(f"{FDC_FOOD}{hit['fdcId']}?api_key={key}")
        nums = {str(n.get("nutrient", {}).get("number", "")): n.get("amount")
                for n in detail.get("foodNutrients", [])}
        if nums.get(PROTEIN) and nums.get(AA_NUM["Met"]):
            return detail["description"], nums
        time.sleep(0.2)
    return None, None


def main():
    key = load_key()
    print(f"Using key: {key[:6]}…  ({'DEMO' if key=='DEMO_KEY' else 'real'})", file=sys.stderr)
    foods = list(csv.DictReader(DATA.open(encoding="utf-8")))

    out_rows = []
    for f in foods:
        slug = f["slug"]
        try:
            desc, nums = find_entry(f.get("fdc_match"), f["name_en"], key)
        except Exception as e:
            print(f"  [err] {f['name_en']}: {e}", file=sys.stderr)
            desc, nums = None, None

        row = {"slug": slug, "name_en": f["name_en"], "fdc_used": desc or "",
               "match": ""}
        if nums:
            protein = nums.get(PROTEIN)
            for col in COLS:
                amt = nums.get(AA_NUM[col])  # g per 100 g food
                row[col] = round(amt * 1000 / protein, 1) if (amt and protein) else ""
            # validation: recomputed Met vs stored Met
            try:
                stored = float(f.get("Met") or 0)
                got = float(row["Met"]) if row["Met"] != "" else 0
                row["match"] = "ok" if abs(stored - got) <= max(2.0, stored * 0.1) else f"DIFF(stored={stored},got={got})"
            except ValueError:
                pass
            print(f"  {f['name_en']:<22} -> {desc[:40]:<40} Met={row.get('Met')} [{row['match']}]", file=sys.stderr)
        else:
            for col in COLS:
                row[col] = ""
            row["match"] = "NO_MATCH"
            print(f"  {f['name_en']:<22} -> NO MATCH", file=sys.stderr)
        out_rows.append(row)
        time.sleep(0.25)

    fields = ["slug", "name_en", "fdc_used", "match"] + COLS
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    ok = sum(1 for r in out_rows if r["match"] == "ok")
    diff = sum(1 for r in out_rows if r["match"].startswith("DIFF"))
    nomatch = sum(1 for r in out_rows if r["match"] == "NO_MATCH")
    print(f"\nDone: {len(out_rows)} foods -> {OUT}", file=sys.stderr)
    print(f"  validated match: {ok}, mismatched: {diff}, no match: {nomatch}", file=sys.stderr)


if __name__ == "__main__":
    main()
