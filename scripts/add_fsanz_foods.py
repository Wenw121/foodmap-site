#!/usr/bin/env python3
"""
Extract amino-acid profiles for a curated set of NEW proteins from the FSANZ
Australian Food Composition Database (Release 3) Excel file and stage candidate
rows for data/foods.csv (+ source column) and data/amino_full.csv.

FSANZ amino values are mg per 100 g; converted to mg per gram of protein.
Download first:
  curl -L -o /tmp/afcd_nutrients.xlsx \
   "https://www.foodstandards.gov.au/sites/default/files/2025-12/AFCD%20Release%203%20-%20Nutrient%20profiles.xlsx"
"""
import csv
import itertools
import openpyxl

XLSX = "/tmp/afcd_nutrients.xlsx"
NAME, PROT = 3, 7
COL = {"Arg": 255, "Cys": 257, "Gly": 259, "His": 260, "Ile": 261, "Leu": 262,
       "Lys": 263, "Met": 264, "Phe": 265, "Thr": 268, "Tyr": 269, "Trp": 270, "Val": 271}
FULL = ["Trp", "Thr", "Ile", "Leu", "Lys", "Met", "Cys", "Phe", "Tyr", "Val", "His", "Arg", "Gly"]

# slug, name_en, name_zh, category_en, category_zh, exact FSANZ Food Name
WANT = [
    ("squid-calamari", "Squid (calamari)", "鱿鱼", "Animal · fish/seafood", "动物 · 鱼/海鲜", "Squid or calamari, raw"),
    ("snapper", "Snapper", "澳洲鲷", "Animal · fish/seafood", "动物 · 鱼/海鲜", "Snapper, fillet, raw"),
    ("bream", "Bream", "黑鲷", "Animal · fish/seafood", "动物 · 鱼/海鲜", "Bream, fillet, raw"),
    ("flathead", "Flathead", "鲬鱼", "Animal · fish/seafood", "动物 · 鱼/海鲜", "Flathead, fillet, raw"),
    ("king-george-whiting", "King George whiting", "乔治王鱚", "Animal · fish/seafood", "动物 · 鱼/海鲜", "Whiting, King George, fillet, raw"),
    ("shark", "Shark", "鲨鱼", "Animal · fish/seafood", "动物 · 鱼/海鲜", "Shark, fillet, without skin, raw"),
    ("goat", "Goat (lean)", "山羊肉", "Animal · red meat", "动物 · 红肉", "Goat, meat, all cuts, lean, raw"),
    ("rabbit", "Rabbit", "兔肉", "Animal · red meat", "动物 · 红肉", "Rabbit, farmed, whole, raw"),
    ("venison", "Venison (lean)", "鹿肉", "Animal · red meat", "动物 · 红肉", "Venison, leg medallion, lean, raw"),
]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    ws = wb["All solids & liquids per 100 g"]
    it = ws.iter_rows(values_only=True)
    for _ in range(3):
        next(it)
    index = {}
    for r in it:
        if r[NAME]:
            index[str(r[NAME]).strip()] = r

    foods_rows, amino_rows = [], []
    for slug, en, zh, cat_en, cat_zh, fname in WANT:
        r = index.get(fname)
        if not r:
            print(f"[MISS] {fname}")
            continue
        prot = num(r[PROT])
        full = {k: (round(num(r[c]) * 1000 / 100 / prot, 1) if num(r[c]) is not None and prot else "")
                for k, c in COL.items()}
        # mg/100g -> mg/g protein = (mg per 100g)/100 / (g protein per 100g) * ...
        # simpler: amino_mg_per_100g / protein_g_per_100g
        full = {k: (round(num(r[c]) / prot, 1) if num(r[c]) is not None and prot else "")
                for k, c in COL.items()}
        leu, ile, val = full["Leu"], full["Ile"], full["Val"]
        bcaa = round(leu + ile + val, 1) if "" not in (leu, ile, val) else ""
        src_label = "Australian Food Composition Database (Release 3), " + fname
        foods_rows.append([slug, en, zh, cat_en, cat_zh, round(prot, 1),
                           full["Met"], full["Cys"], full["Leu"], bcaa, full["Arg"],
                           full["Gly"], full["Trp"], "", "", src_label, "FSANZ"])
        amino_rows.append([slug, en, src_label, "fsanz"] + [full[k] for k in FULL])
        print(f"{en:<22} -> {fname[:40]:<40} prot={prot} Met={full['Met']} Lys={full['Lys']} BCAA={bcaa}")

    with open("/tmp/fsanz_new_foods.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(foods_rows)
    with open("/tmp/fsanz_new_amino.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(amino_rows)
    print(f"\nStaged {len(foods_rows)} foods")


if __name__ == "__main__":
    main()
