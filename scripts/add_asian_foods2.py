#!/usr/bin/env python3
"""
Second batch of Asian-relevant foods from USDA FoodData Central (full amino
profiles). Stages rows for data/foods.csv (with source=USDA) and
data/amino_full.csv. Foods lacking amino data in USDA are skipped.
"""
import csv, json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FDC_SEARCH = "https://api.nal.usda.gov/fdc/v1/foods/search"
FDC_FOOD = "https://api.nal.usda.gov/fdc/v1/food/"
PROTEIN = "203"
AA_NUM = {"Trp":"501","Thr":"502","Ile":"503","Leu":"504","Lys":"505","Met":"506",
          "Cys":"507","Phe":"508","Tyr":"509","Val":"510","Arg":"511","His":"512","Gly":"516"}
FULL = ["Trp","Thr","Ile","Leu","Lys","Met","Cys","Phe","Tyr","Val","His","Arg","Gly"]

# slug, name_en, name_zh, category_en, category_zh, USDA query
NEW = [
    ("miso","Miso","味噌","Plant · legumes","植物 · 豆类","Miso"),
    ("octopus","Octopus","章鱼","Animal · fish/seafood","动物 · 鱼/海鲜","Mollusks, octopus, common, raw"),
    ("abalone","Abalone","鲍鱼","Animal · fish/seafood","动物 · 鱼/海鲜","Mollusks, abalone, mixed species, raw"),
    ("mussels","Mussels","贻贝","Animal · fish/seafood","动物 · 鱼/海鲜","Mollusks, mussel, blue, raw"),
    ("clams","Clams","蛤蜊","Animal · fish/seafood","动物 · 鱼/海鲜","Mollusks, clam, mixed species, raw"),
    ("pompano","Pompano","鲳鱼","Animal · fish/seafood","动物 · 鱼/海鲜","Fish, pompano, florida, raw"),
    ("taro","Taro","芋头","Plant · vegetables/algae","植物 · 蔬菜/藻类","Taro, raw"),
    ("lotus-seeds","Lotus seeds","莲子","Plant · seeds","植物 · 种子","Lotus seeds, dried"),
    ("kimchi","Kimchi","泡菜","Plant · vegetables/algae","植物 · 蔬菜/藻类","Kimchi"),
    ("napa-cabbage","Napa cabbage","大白菜","Plant · vegetables/algae","植物 · 蔬菜/藻类","Cabbage, napa, cooked"),
    ("wood-ear","Wood ear mushroom","木耳","Plant · vegetables/algae","植物 · 蔬菜/藻类","Mushrooms, Cloud ears, dried"),
    ("bamboo-shoots","Bamboo shoots","竹笋","Plant · vegetables/algae","植物 · 蔬菜/藻类","Bamboo shoots, raw"),
]

def load_key():
    key=os.environ.get("USDA_API_KEY")
    if not key:
        envf=ROOT/".env"
        if envf.exists():
            for ln in envf.read_text().splitlines():
                if ln.startswith("USDA_API_KEY="): key=ln.split("=",1)[1].strip()
    return key or "DEMO_KEY"

def get(url):
    req=urllib.request.Request(url, headers={"User-Agent":"FoodMap/2.0"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)

FORCE_ID={"octopus":174218,"abalone":174212,"mussels":174216,"napa-cabbage":168572,"wood-ear":168581}

def fetch_by_id(fid,key):
    detail=get(f"{FDC_FOOD}{fid}?api_key={key}")
    nums={str(n.get('nutrient',{}).get('number','')):n.get('amount') for n in detail.get('foodNutrients',[])}
    return detail["description"], nums

def find_entry(query, key):
    qs=urllib.parse.urlencode({"api_key":key,"query":query,"dataType":"SR Legacy,Foundation","pageSize":25})
    hits=get(f"{FDC_SEARCH}?{qs}").get("foods",[])
    if not hits: return None,None
    target=query.strip().lower()
    def score(h):
        d=h.get("description","").strip().lower()
        if d==target: return 1000
        toks=target.replace(","," ").split()
        return sum(1 for t in toks if t in d)
    for hit in sorted(hits,key=score,reverse=True)[:5]:
        detail=get(f"{FDC_FOOD}{hit['fdcId']}?api_key={key}")
        nums={str(n.get('nutrient',{}).get('number','')):n.get('amount') for n in detail.get('foodNutrients',[])}
        if nums.get(PROTEIN) and nums.get(AA_NUM["Met"]):
            return detail["description"], nums
        time.sleep(0.2)
    return None,None

def mgg(nums,col,prot):
    a=nums.get(AA_NUM[col]); return round(a*1000/prot,1) if (a and prot) else ""

def main():
    key=load_key(); print(f"key {key[:6]}…",file=sys.stderr)
    foods,amino=[],[]
    for slug,en,zh,ce,cz,q in NEW:
        try:
            if slug in FORCE_ID: desc,nums=fetch_by_id(FORCE_ID[slug],key)
            else: desc,nums=find_entry(q,key)
        except Exception as e: print(f"[ERR] {en}: {e}",file=sys.stderr); continue
        if not nums: print(f"[SKIP no amino] {en} ({q})",file=sys.stderr); continue
        p=nums.get(PROTEIN); full={c:mgg(nums,c,p) for c in FULL}
        leu,ile,val=full["Leu"],full["Ile"],full["Val"]
        bcaa=round(leu+ile+val,1) if "" not in (leu,ile,val) else ""
        foods.append([slug,en,zh,ce,cz,p,full["Met"],full["Cys"],full["Leu"],bcaa,
                      full["Arg"],full["Gly"],full["Trp"],"","",desc,"USDA"])
        amino.append([slug,en,desc,"added2"]+[full[c] for c in FULL])
        print(f"{en:<18} -> {desc[:42]:<42} prot={p} Met={full['Met']} Lys={full['Lys']} BCAA={bcaa}",file=sys.stderr)
    csv.writer(open("/tmp/asian2_foods.csv","w",newline="",encoding="utf-8")).writerows(foods)
    csv.writer(open("/tmp/asian2_amino.csv","w",newline="",encoding="utf-8")).writerows(amino)
    print(f"\nStaged {len(foods)} foods",file=sys.stderr)

if __name__=="__main__": main()
