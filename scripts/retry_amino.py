#!/usr/bin/env python3
"""Retry the foods that failed in fetch_amino.py, using clean simple queries,
and patch data/amino_full.csv in place."""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AMINO = ROOT / "data" / "amino_full.csv"
FOODS = ROOT / "data" / "foods.csv"
FDC_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_FOOD = "https://api.nal.usda.gov/fdc/v1/food/"
PROTEIN = "203"
AA_NUM = {"Trp": "501", "Thr": "502", "Ile": "503", "Leu": "504", "Lys": "505",
          "Met": "506", "Cys": "507", "Phe": "508", "Tyr": "509", "Val": "510",
          "Arg": "511", "His": "512", "Gly": "516"}
COLS = ["Trp", "Thr", "Ile", "Leu", "Lys", "Met", "Cys", "Phe", "Tyr", "Val", "His", "Arg", "Gly"]

# clean queries for the 8 that failed
RETRY = {
    "beef-sirloin": "beef top sirloin steak raw",
    "broccoli": "broccoli raw",
    "brown-rice": "rice brown long-grain raw",
    "chickpeas": "chickpeas garbanzo mature raw",
    "ground-beef": "beef ground 70 raw",
    "lamb-leg": "lamb leg whole raw",
    "pork-loin": "pork loin top loin boneless raw",
    "whole-milk": "milk whole 3.25 milkfat",
}


def load_key():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("USDA_API_KEY="):
            return line.split("=", 1)[1].strip()
    return "DEMO_KEY"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "FoodMap/2.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch(query, key):
    qs = urllib.parse.urlencode({"api_key": key, "query": query,
                                 "dataType": "SR Legacy,Foundation", "pageSize": 15})
    hits = get(f"{FDC_SEARCH}?{qs}").get("foods", [])
    for hit in hits[:5]:
        detail = get(f"{FDC_FOOD}{hit['fdcId']}?api_key={key}")
        nums = {str(n.get("nutrient", {}).get("number", "")): n.get("amount")
                for n in detail.get("foodNutrients", [])}
        if nums.get(PROTEIN) and nums.get(AA_NUM["Met"]):
            return detail["description"], nums
        time.sleep(0.2)
    return None, None


def main():
    key = load_key()
    stored_met = {r["slug"]: r.get("Met") for r in csv.DictReader(FOODS.open(encoding="utf-8"))}
    rows = list(csv.DictReader(AMINO.open(encoding="utf-8")))
    by_slug = {r["slug"]: r for r in rows}

    for slug, query in RETRY.items():
        try:
            desc, nums = fetch(query, key)
        except Exception as e:
            print(f"  [err] {slug}: {e}", file=sys.stderr); continue
        if not nums:
            print(f"  {slug}: still no match", file=sys.stderr); continue
        protein = nums.get(PROTEIN)
        row = by_slug[slug]
        row["fdc_used"] = desc
        for col in COLS:
            amt = nums.get(AA_NUM[col])
            row[col] = round(amt * 1000 / protein, 1) if (amt and protein) else ""
        try:
            sm = float(stored_met.get(slug) or 0); gm = float(row["Met"] or 0)
            row["match"] = "ok" if abs(sm - gm) <= max(2.0, sm * 0.1) else f"DIFF(stored={sm},got={gm})"
        except ValueError:
            row["match"] = "?"
        print(f"  {slug:<14} -> {desc[:42]:<42} Met={row['Met']} [{row['match']}]", file=sys.stderr)
        time.sleep(0.3)

    fields = ["slug", "name_en", "fdc_used", "match"] + COLS
    with AMINO.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["match"] == "ok")
    print(f"\nPatched. validated now: {ok}/{len(rows)}", file=sys.stderr)


if __name__ == "__main__":
    main()
