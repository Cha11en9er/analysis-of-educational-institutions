# -*- coding: utf-8 -*-
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

out = Path(__file__).resolve().parent
path = out / "6abd169c53586.xlsx"
df = pd.read_excel(path, sheet_name="2026-2027", header=2)
name_col = df.columns[3]
short = df.columns[4]
df = df.dropna(subset=[name_col]).copy()
df["name"] = df[name_col].astype(str).str.strip()
df["short"] = df[short].astype(str).str.replace("\n", " ", regex=False).str.strip()
df["code"] = pd.to_numeric(df["Код ОО"], errors="coerce")
df["ate"] = pd.to_numeric(df["Код АТЕ"], errors="coerce")


def is_preschool(n: str) -> bool:
    n = n.lower()
    return bool(
        re.search(
            r"дошкольн|детский сад|ясли|мбдоу|мадоу|мкдоу|мдоу",
            n,
        )
    )


def is_vuz(n: str) -> bool:
    n = n.lower()
    if re.search(r"дополнительн.*профессион|повышения квалификации|дпо\b", n):
        return False
    return bool(
        re.search(
            r"универс|институт(?!.*дошколь)|академи|высш(ее|его)\s+образован",
            n,
        )
    )


def is_college(n: str) -> bool:
    n = n.lower()
    return bool(
        re.search(
            r"колледж|техникум|профессиональн(ое|ого)\s+образован|училище",
            n,
        )
    )


presch = df[df["name"].map(is_preschool)].copy()
vuz = df[df["name"].map(is_vuz)].copy()
col = df[df["name"].map(is_college)].copy()

presch["in_city"] = presch["ate"].between(242, 249) | presch["name"].str.contains(
    r"г\.?\s*Саратов|города Саратова", case=False, na=False
)

print("preschool", len(presch), "cityish", int(presch["in_city"].sum()))
print("vuz_like", len(vuz), "college", len(col))
print("ATE top preschool:", Counter(presch["ate"].dropna().astype(int)).most_common(12))

city_p = presch[presch["in_city"]]
pat = Counter()
for n in city_p["name"]:
    nl = n.lower()
    if "комбинирован" in nl:
        pat["combined"] += 1
    elif "компенсир" in nl:
        pat["compensating"] += 1
    elif "общеразвив" in nl:
        pat["general_dev"] += 1
    elif "центр развития" in nl or "црр" in nl:
        pat["crr"] += 1
    elif "присмотр" in nl or "оздоровлен" in nl:
        pat["health"] += 1
    else:
        pat["other"] += 1
print("city preschool subtypes", dict(pat))

print("--- city preschool sample ---")
for _, r in city_p.head(20).iterrows():
    ate = int(r["ate"]) if pd.notna(r["ate"]) else None
    code = int(r["code"]) if pd.notna(r["code"]) else None
    print(ate, code, r["short"][:90])

print("--- vuz in registry ---")
for _, r in vuz.iterrows():
    print(r["ate"], r["code"], r["name"][:130])

print("--- college sample ---")
for _, r in col.head(15).iterrows():
    ate = int(r["ate"]) if pd.notna(r["ate"]) else None
    code = int(r["code"]) if pd.notna(r["code"]) else None
    print(ate, code, r["short"][:100])


def row_dict(r):
    return {
        "ate": None if pd.isna(r["ate"]) else int(r["ate"]),
        "code_oo": None if pd.isna(r["code"]) else int(r["code"]),
        "name": r["name"],
        "short": r["short"],
    }


payload = {
    "preschool_total_region": len(presch),
    "preschool_city_count": len(city_p),
    "preschool_city_subtypes": dict(pat),
    "preschool_city": [row_dict(r) for _, r in city_p.iterrows()],
    "preschool_region_all": [row_dict(r) for _, r in presch.iterrows()],
    "vuz_in_rcoko_registry": [row_dict(r) for _, r in vuz.iterrows()],
    "college_spo": [row_dict(r) for _, r in col.iterrows()],
}
(out / "found_preschool_and_vuz_from_registry.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("wrote", out / "found_preschool_and_vuz_from_registry.json")
