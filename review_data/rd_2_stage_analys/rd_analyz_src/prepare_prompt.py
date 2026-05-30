# -*- coding: utf-8 -*-
"""Сборка промптов для пошкольного анализа отзывов."""

from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROMPT_TEMPLATE_DIR = BASE / "rd_analys_prompt" / "rd_analys_prompt_template"
PROMPT_BIG_ANALYZ = PROMPT_TEMPLATE_DIR / "prompt_big_analyz.txt"
PROMPT_BIG_LLM = PROMPT_TEMPLATE_DIR / "prompt_big_llm.txt"
REVIEWS_DIR = BASE.parent / "rd_2_stage" / "rd_separately"
OUT_DIR = BASE / "rd_analys_prompt" / "rd_analys_prompt_final"
OUTPUT_ANALYZED_DIR = BASE / "rd_separately_analyzed"

REVIEWS_PATTERN = re.compile(r"school_reviews_separately_(\d+)\.json")


def save_output_instruction(school_num: str) -> str:
    """Инструкция для LLM: куда сохранить результат анализа."""
    filename = f"school_reviews_separately_{school_num}_analyz.json"
    folder = OUTPUT_ANALYZED_DIR.resolve()
    return (
        f"\n\nполученный json файл сохрани в {folder} "
        f"под названием {filename}"
    )


def main() -> None:
    with open(PROMPT_BIG_ANALYZ, encoding="utf-8") as f:
        prompt_big = f.read()
    single_line_prompt = " ".join(prompt_big.split())

    with open(PROMPT_BIG_LLM, encoding="utf-8") as f:
        llm_template = f.read()

    parts = re.split(r"(---промпт---|---отзывы---)", llm_template)
    head = parts[0] + parts[1] + parts[2]
    middle = parts[3] + parts[4] + parts[5] + parts[6]
    tail = parts[7] + parts[8]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_ANALYZED_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for path in sorted(
        REVIEWS_DIR.glob("school_reviews_separately_*.json"),
        key=lambda p: int(REVIEWS_PATTERN.match(p.name).group(1))
        if REVIEWS_PATTERN.match(p.name)
        else 0,
    ):
        match = REVIEWS_PATTERN.match(path.name)
        if not match:
            continue
        num = match.group(1)
        reviews_content = path.read_text(encoding="utf-8")
        final_text = (
            head
            + single_line_prompt
            + middle
            + reviews_content
            + tail
            + save_output_instruction(num)
        )
        out_path = OUT_DIR / f"sr_analys_prompt_final_separately_{num}.txt"
        out_path.write_text(final_text, encoding="utf-8")
        written += 1
        print("Записано:", out_path)

    print("Готово. Файлов:", written)


if __name__ == "__main__":
    main()
