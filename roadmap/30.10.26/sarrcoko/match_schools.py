#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сопоставление наших школ (final_school_data.json) с кодами ОО каталога РЦОКО."""
import json, re

def norm(s):
    s = (s or '').lower().replace('ё', 'е')
    s = re.sub(r'[«»"\'`]', '', s)
    s = re.sub(r'моу|маоу|гаоу|гбоу|мбдо|мбоу|гбпоу|со г\.саратова|им\.|имени', ' ', s)
    s = re.sub(r'г\. ?саратова?|саратовская обл\.?|саратовской обл\.?', ' ', s)
    s = re.sub(r'[^а-яa-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def tokens(s):
    return set(norm(s).split())

orgs = json.load(open('roadmap/30.10.26/sarrcoko/rcoko_orgs.json', encoding='utf-8'))
final = json.load(open('school_data/final_school_data.json', encoding='utf-8'))

# индекс РЦОКО: номер школы+тип -> org
def school_key_feats(name):
    raw = (name or '').lower()
    n = norm(name)
    m = re.search(r'школа\s*(?:№\s*)?(\d+)', n) or re.search(r'(?:№|n)\s*(\d+)', raw)
    num = m.group(1) if m else None
    typ = []
    for t, pat in [('lyceum', 'лицей'), ('gymnasium', 'гимназ'), ('progym', 'прогимназ'), ('soosh', 'средняя'), ('oosh', 'основная')]:
        if re.search(pat, n):
            typ.append(t)
    return num, typ, n

matched = {}
for o in orgs:
    num, typ, n = school_key_feats(o['name_full'] or o['name_short'])
    keys = [f'{t}:{num}' for t in typ] if num else []
    keys.append(f'all:{num}' if num else None)
    if not num:
        keys = ['notype:' + ' '.join(sorted(tokens(o['name_full'] or o['name_short']))[:3])]
    for k in keys:
        if k:
            matched.setdefault(k, []).append((o, typ, n))

def plausible(sch, o):
    oname = (o.get('name_full') or '') + ' ' + (o.get('name_short') or '')
    if re.search(r'детский сад|дошколь|дмш|дхш|дюсш|сшор|музыкальн|художеств|хореограф', oname):
        return False  # наша выборка — школы, не садики
    addr = (o.get('address') or '').lower()
    # все наши школы — Саратов/пригороды Саратовского района
    if 'г. саратов' not in addr and 'саратовск' not in addr.replace('саратовская обл.', ''):
        return False
    if re.search(r'г\. [а-я]+,', addr) and 'саратов' not in addr.split('г. ')[1][:12]:
        return False  # другой город области (Аткарск, Балаково...)
    return True

result = []
unmatched = []
for sch in final:
    num, typ, n = school_key_feats(sch.get('short_name') or sch.get('name_2gis'))
    stoks = tokens(sch.get('short_name') or '')
    if num:
        keys = [f'{t}:{num}' for t in typ] + [f'all:{num}']
        best, best_score = None, -1
        for k in keys:
            for o, otyp, on in matched.get(k, []):
                if not plausible(sch, o):
                    continue
                score = 0
                common = tokens(sch.get('address') or '') & tokens(o.get('address') or '')
                score += len(common) * 3
                score += len(set(typ) & set(otyp)) * 2
                score += len(stoks & tokens(o.get('name_full') or o.get('name_short') or ''))
                if score > best_score:
                    best, best_score = o, score
    else:
        # без номера: линейный поиск по токенам имени (минимум 2 общих значимых)
        best, best_score = None, -1
        for o in orgs:
            if not plausible(sch, o):
                continue
            otk = tokens(o['name_full'] or '') | tokens(o['name_short'] or '')
            common_name = stoks & otk - {'школа', 'лицей', 'гимназия', 'мбоу', 'маоу', 'моу', 'гаоу', 'гбоу', 'ано', 'аноо', 'чоу', 'саратова', 'саратов'}
            if len(common_name) < 2:
                continue
            score = len(common_name) * 3 + len(tokens(sch.get('address') or '') & tokens(o.get('address') or '')) * 3
            if score > best_score:
                best, best_score = o, score
    if best and best_score >= 4:
        result.append({
            'school_id': sch['id'], 'name': sch.get('short_name') or sch.get('name_2gis'),
            'code_oo': best['code_oo'], 'rcoko_name': best['name_short'],
            'score': best_score,
        })
    else:
        unmatched.append({'school_id': sch['id'], 'name': sch.get('short_name')})

print('matched:', len(result), '| unmatched:', len(unmatched))
for r in result[:8]:
    print(r['school_id'], r['name'], '->', r['code_oo'], r['rcoko_name'][:40], 'score', r['score'])
for u in unmatched[:12]:
    print('MISS', u['school_id'], u['name'])

json.dump({'matched': result, 'unmatched': unmatched},
          open('roadmap/30.10.26/sarrcoko/schools_to_code_oo.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
