# -*- coding: utf-8 -*-
import re
from pathlib import Path

# Пути (от корня репозитория или абсолютные)
BASE = Path(__file__).resolve().parent.parent
PROMPT_BIG_ANALYZ = BASE / 'sr_analys_prompt' / 'sr_analys_prompt_template' / 'prompt_big_analyz.txt'
PROMPT_BIG_LLM = BASE / 'sr_analys_prompt' / 'sr_analys_prompt_template' / 'prompt_big_llm.txt'
SR_SEPARATELY_DIR = BASE / 'sr_separately'
OUT_DIR = BASE / 'sr_analys_prompt' / 'sr_analys_prompt_final'

# 1. Большой промпт в одну строку
with open(PROMPT_BIG_ANALYZ, 'r', encoding='utf-8') as f:
    prompt_big = f.read()
single_line_prompt = ' '.join(prompt_big.split())

# 2. Шаблон prompt_big_llm: между строками 1–3 вставляем промпт, между 4–6 — отзывы
with open(PROMPT_BIG_LLM, 'r', encoding='utf-8') as f:
    llm_template = f.read()

# Разбиваем по маркерам: до первого ---промпт---, между ---промпт--- и ---отзывы---, после ---отзывы---
parts = re.split(r'(---промпт---|---отзывы---)', llm_template)
# parts: ['', '---промпт---', '\n\n', '---промпт---', '\n', '---отзывы---', '\n\n', '---отзывы---', '\n\nпроанализируй...']
# Собираем: head + single_line_prompt + middle + reviews + tail
head = parts[0] + parts[1] + parts[2]           # "---промпт---\n\n"
middle = parts[3] + parts[4] + parts[5] + parts[6]  # "---промпт---\n---отзывы---\n\n"
tail = parts[7] + parts[8]                        # "---отзывы---\n\nпроанализируй..."

OUT_DIR.mkdir(parents=True, exist_ok=True)

# 3. Цикл по файлам в sr_separately
pattern = re.compile(r'school_reviews_separately_(\d+)\.json')
for path in sorted(SR_SEPARATELY_DIR.glob('school_reviews_separately_*.json'), key=lambda p: int(pattern.match(p.name).group(1)) if pattern.match(p.name) else 0):
    m = pattern.match(path.name)
    if not m:
        continue
    num = m.group(1)
    with open(path, 'r', encoding='utf-8') as f:
        reviews_content = f.read()
    final_text = head + single_line_prompt + middle + reviews_content + tail
    out_path = OUT_DIR / f'sr_analys_prompt_final_separately_{num}.txt'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final_text)
    print('Записано:', out_path)

print('Готово. Файлов:', len(list(OUT_DIR.glob('sr_analys_prompt_final_separately_*.txt'))))
