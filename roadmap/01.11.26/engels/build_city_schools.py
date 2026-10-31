#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка city_schools.json: школы Энгельса из РЦОКО + координаты из sa.institution + ссылки."""
import json

coords = {x["code_oo"]: x for x in json.load(open("/tmp/inst_coords.json", encoding="utf-8"))}
schools = json.load(open("/tmp/engels_schools.json", encoding="utf-8"))
ym = json.load(open("/tmp/ym_orgs_engels.json", encoding="utf-8"))

out = []
for s in schools:
    code = s["code_oo"]
    ic = coords.get(code)
    if not ic:
        print("skip (no coords):", code, s["name"][:40])
        continue
    yorgs = ym.get(str(code)) or []
    site = s.get("site")
    if site and site.startswith("//"):
        site = "https:" + site
    yandex_url = None
    if yorgs:
        yandex_url = "https://yandex.ru/maps/org/{}/{}".format(yorgs[0][0], yorgs[0][1])
    out.append({
        "school_id": 100000 + code,
        "code_oo": code,
        "name_full": s["name_full"] or s["name"],
        "name_short": s["name"],
        "city": "Энгельс",
        "ownership": s.get("ownership") or "public",
        "address": s["address"],
        "site": site,
        "link_yandex": yandex_url,
        "latitude": ic["latitude"],
        "longitude": ic["longitude"],
    })

json.dump(out, open("/tmp/city_schools.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ready:", len(out))
