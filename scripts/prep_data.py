#!/usr/bin/env python3
"""
Prepare a standardized, bilingual master data file for the methionine food map.

Reads the existing amino-acid matrix (../foodmap/food_amino_map.csv) and emits
data/foods.csv with stable slugs, English + Chinese names, and bilingual
category labels. This is the ONLY data file the site generator (build.py) reads,
so the site stays buildable even if the upstream pipeline changes.

Usage:
    python scripts/prep_data.py            # reads ../foodmap/food_amino_map.csv
    SOURCE_CSV=/path/to.csv python scripts/prep_data.py
"""
import csv
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE_CSV = Path(
    os.environ.get("SOURCE_CSV", ROOT.parent / "foodmap" / "food_amino_map.csv")
)
OUT_CSV = ROOT / "data" / "foods.csv"

# English food name -> Chinese name
NAME_ZH = {
    "Cottage cheese": "茅屋芝士",
    "Greek yogurt": "希腊酸奶",
    "Cheddar cheese": "切达奶酪",
    "Parmesan cheese": "帕玛森奶酪",
    "Whole milk": "全脂牛奶",
    "Whey protein isolate": "分离乳清蛋白",
    "Mozzarella": "马苏里拉奶酪",
    "Egg white": "蛋清",
    "Whole egg": "全蛋",
    "Egg yolk": "蛋黄",
    "Beef liver": "牛肝",
    "Pork loin": "猪里脊（大里脊）",
    "Pork tenderloin (lean)": "猪里脊（小里脊·瘦）",
    "Beef sirloin": "牛西冷",
    "Ground beef": "牛肉糜",
    "Lamb leg": "羊腿",
    "Bacon": "培根",
    "Pork sausage": "猪肉香肠",
    "Ham (cured)": "火腿（腌制）",
    "Duck": "鸭肉",
    "Chicken thigh": "鸡腿肉",
    "Chicken breast": "鸡胸肉",
    "Turkey breast": "火鸡胸肉",
    "Tuna": "金枪鱼",
    "Sardines": "沙丁鱼",
    "Mackerel": "鲭鱼",
    "Grouper": "石斑鱼",
    "Sea bass": "鲈鱼",
    "Cod": "鳕鱼",
    "Atlantic salmon": "大西洋鲑鱼（三文鱼）",
    "Shrimp": "虾",
    "Tilapia": "罗非鱼",
    "Crab": "蟹",
    "Oysters": "牡蛎",
    "Scallops": "扇贝",
    "Soybeans": "黄豆（大豆）",
    "Black beans": "黑豆",
    "Kidney beans": "红芸豆",
    "Tofu": "豆腐",
    "Mung beans": "绿豆",
    "Natto": "纳豆",
    "Chickpeas": "鹰嘴豆",
    "Edamame (green soy)": "毛豆",
    "Pinto beans": "斑豆",
    "Lentils": "扁豆（小扁豆）",
    "Tempeh": "天贝",
    "Green peas": "青豌豆",
    "Millet": "小米",
    "Corn": "玉米",
    "Brown rice": "糙米",
    "White rice": "白米",
    "Oats": "燕麦",
    "Wheat germ": "小麦胚芽",
    "Barley": "大麦",
    "Wheat (hard)": "硬质小麦",
    "Quinoa": "藜麦",
    "Soba noodles": "荞麦面",
    "Buckwheat": "荞麦",
    "Brazil nuts": "巴西坚果",
    "Cashews": "腰果",
    "Pistachios": "开心果",
    "Walnuts": "核桃",
    "Hazelnuts": "榛子",
    "Pecans": "碧根果（美国山核桃）",
    "Peanuts": "花生",
    "Almonds": "杏仁（巴旦木）",
    "Chia seeds": "奇亚籽",
    "Sesame seeds": "芝麻",
    "Sunflower seeds": "葵花籽",
    "Pumpkin seeds": "南瓜籽",
    "Flaxseed": "亚麻籽",
    "Hemp seeds": "火麻仁（大麻籽）",
    "Spirulina (dried)": "螺旋藻（干）",
    "Shiitake mushroom": "香菇",
    "Spinach": "菠菜",
    "Sweet potato": "红薯",
    "Yam": "山药",
    "Potato": "马铃薯（土豆）",
    "Enoki mushroom": "金针菇",
    "Broccoli": "西兰花",
    "White mushroom": "白蘑菇",
    "Turmeric (ground)": "姜黄粉",
    "Cinnamon (ground)": "肉桂粉",
    "Gelatin": "明胶",
}

# Raw category -> (English label, Chinese label)
CATEGORY_MAP = {
    "Animal · whey/dairy": ("Animal · whey/dairy", "动物 · 乳清/乳制品"),
    "Animal · eggs": ("Animal · eggs", "动物 · 蛋类"),
    "Animal · red meat": ("Animal · red meat", "动物 · 红肉"),
    "Animal · processed meat": ("Animal · processed meat", "动物 · 加工肉"),
    "Animal · poultry": ("Animal · poultry", "动物 · 禽肉"),
    "Animal · fish/seafood": ("Animal · fish/seafood", "动物 · 鱼/海鲜"),
    "Plant · legumes": ("Plant · legumes", "植物 · 豆类"),
    "Plant · grains": ("Plant · grains", "植物 · 谷物"),
    "Plant · nuts": ("Plant · nuts", "植物 · 坚果"),
    "Plant · seeds": ("Plant · seeds", "植物 · 种子"),
    "Plant · vegetables/algae": ("Plant · vegetables/algae", "植物 · 蔬菜/藻类"),
    "Spice · seasoning": ("Spice · seasoning", "香料 · 调味"),
    "Special · collagen": ("Special · collagen", "特殊 · 胶原蛋白"),
}


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[()]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def main() -> None:
    if not SOURCE_CSV.exists():
        raise SystemExit(f"Source CSV not found: {SOURCE_CSV}")

    rows = []
    slugs = set()
    with SOURCE_CSV.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            name_en = (r.get("food") or "").strip()
            if not name_en:
                continue
            raw_cat = (r.get("category") or "").strip()
            cat_en, cat_zh = CATEGORY_MAP.get(raw_cat, (raw_cat, raw_cat))
            name_zh = NAME_ZH.get(name_en)
            if name_zh is None:
                print(f"  [warn] no Chinese name for: {name_en!r}")
                name_zh = name_en
            slug = slugify(name_en)
            if slug in slugs:
                raise SystemExit(f"Duplicate slug: {slug}")
            slugs.add(slug)
            rows.append(
                {
                    "slug": slug,
                    "name_en": name_en,
                    "name_zh": name_zh,
                    "category_en": cat_en,
                    "category_zh": cat_zh,
                    "protein_g_100g": (r.get("protein_g_100g") or "").strip(),
                    "Met": (r.get("Met") or "").strip(),
                    "Cys": (r.get("Cys") or "").strip(),
                    "Leu": (r.get("Leu") or "").strip(),
                    "BCAA": (r.get("BCAA") or "").strip(),
                    "Arg": (r.get("Arg") or "").strip(),
                    "Gly": (r.get("Gly") or "").strip(),
                    "Trp": (r.get("Trp") or "").strip(),
                    "diaas": (r.get("diaas") or "").strip(),
                    "diaas_limit": (r.get("diaas_limit") or "").strip(),
                    "fdc_match": (r.get("fdc_match") or "").strip(),
                }
            )

    rows.sort(key=lambda x: x["name_en"].lower())
    fields = [
        "slug", "name_en", "name_zh", "category_en", "category_zh",
        "protein_g_100g", "Met", "Cys", "Leu", "BCAA", "Arg", "Gly", "Trp",
        "diaas", "diaas_limit", "fdc_match",
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} foods -> {OUT_CSV}")


if __name__ == "__main__":
    main()
