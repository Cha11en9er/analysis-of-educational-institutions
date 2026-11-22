#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Разметка отзывов по темам — реализация правил промпта
review_data/rd_2_stage_analys/rd_analys_prompt/rd_analys_prompt_template/prompt_big_analyz.txt.

Правила промпта:
  - 8 тем, только явно упомянутые (ключевые слова + синонимы + однокоренные);
  - тональность темы — по контексту упоминания;
  - overall: rating<=2 -> neg, rating>=4 -> pos, rating==3 -> нейтраль по умолчанию,
    но явные позитивные/негативные слова перебивают;
  - «директор/завуч/руководитель» -> администрация (не учителя);
  - «парта/мебель/оборудование» -> инфраструктура;
  - предметы -> учителя;
  - тем нет -> topics = {}.

Запуск:
  python db/db_src/db_insert/analyze_reviews.py --in raw.json --out analyz.json
"""
import argparse
import json
import re

# --- темы: регулярки (слово + однокоренные + синонимы) ---
TOPICS = {
    "ремонт": [
        r"ремонт", r"стен[аеуыой]?\b", r"трещин", r"туалет", r"мозаик", r"асфальт",
        r"потолок", r"пол(?:а|ы|ов|ом|у)?\b", r"окн[а-я]*", r"двер[а-я]*",
        r"отоплени", r"тепл[а-я]*", r"протека", r"теч[еи]", r"штукатурк", r"побелк",
        r"краск[аи]", r"ремонтн",
    ],
    "учителя": [
        r"учител[а-я]*", r"преподавател[а-я]*", r"педагог[а-я]*", r"воспитател[а-я]*",
        r"классн\w*\s*руководител", r"учительск", r"преподавательск", r"предмет\w*",
        r"урок\w*", r"обучени[еяю]", r"преподавани[еяю]", r"репетитор\w*",
        r"отношени\w*\s*(?:учител|преподавател)", r"уч[ае]т[ьи]\b", r"ученик\w*",
        r"училищ\w*", r"наставник\w*", r"воспитани[еяю]",
        r"учатся", r"учусь", r"учиться", r"учился", r"учитесь", r"учатся\w*",
    ],
    "еда": [
        r"еда\w*", r"корм\w*", r"столов\w*", r"питани[еяю]", r"отравлени", r"обед\w*",
        r"завтрак\w*", r"меню\w*", r"каш[аеу]", r"суп\w*", r"компот", r"бутерброд",
        r"столовк\w*", r"ж\w*л[а-я]*\s*столов", r"питание",
    ],
    "администрация": [
        r"директор\w*", r"завуч\w*", r"руководител[а-я]*", r"администраци[яю]",
        r"управлени[еяю]", r"директора", r"завуч\b",
    ],
    "буллинг": [
        r"травл[а-я]*", r"буллинг\w*", r"обид[а-я]*", r"обиж[а-я]*", r"бь[её]?т\w*",
        r"конфликт\w*", r"ссор\w*", r"сор\w*", r"дружелюб", r"атмосфер\w*",
        r"семь[ья]", r"изоляц", r"унижа", r"оскорбл",
    ],
    "инфраструктура": [
        r"парков\w*", r"пространств\w*", r"спортзал\w*", r"бассейн\w*", r"стадион\w*",
        r"площадк\w*", r"кабинет\w*", r"оборудовани[еяю]", r"стоянк\w*", r"дорог\w*",
        r"техник\w*", r"мебел\w*", r"подъезд\w*", r"парта\w*", r"здани[еяю]", r"класс\w*",
        r"территори[яю]", r"двор\w*", r"гимнаст\w*", r"раздевалк",
        r"коридор\w*",
    ],
    "охрана": [
        r"охрана\w*", r"охрану", r"безопасност\w*", r"пропуск\w*", r"вход\w*",
        r"выход\w*", r"охра\w*", r"турник\w*", r"видеонаблюден", r"пожарн\w*",
    ],
    "уборка": [
        r"уборк\w*", r"чистот\w*", r"чист[а-я]*", r"грязн\w*", r"мусор\w*", r"санитари\w*",
        r"вытрях\w*", r"убра\w*", r"мыт[ьи]", r"вымыв\w*", r"уборочн",
    ],
}
COMPILED = {topic: [re.compile(p, re.IGNORECASE) for p in pats] for topic, pats in TOPICS.items()}

POSITIVE = [
    r"хорош\w*", r"отличн\w*", r"прекрасн\w*", r"замечательн\w*", r"великолеп\w*",
    r"лучш\w*", r"люблю", r"нравит\w*", r"благодар\w*", r"спасибо", r"сильн\w*",
    r"умн\w*", r"ответственн\w*", r"забот\w*", r"внимательн\w*", r"профессионал\w*",
    r"справедлив\w*", r"чист\w*", r"уютн\w*", r"красив\w*", r"современн\w*", r"нов\w*",
    r"вкусн\w*", r"вкусно", r"качественн\w*", r"добр\w*", r"вежлив\w*", r"помог\w*",
    r"поддерж\w*", r"друж\w*", r"дружелюб", r"готов\w*", r"справля\w*", r"образован\w*",
    r"молодцы", r"знающ\w*", r"предан\w*", r"любя", r"продвинут\w*", r"доброжелат\w*",
    r"терпелив\w*", r"внимательн\w*", r"здорово", r"хвалить", r"береж\w*", r"аккуратн\w*",
    r"ухоженн\w*", r"ухож\w*", r"свеж\w*", r"тепл\w*", r"светл\w*", r"просторн\w*",
    r"благодар\w*", r"счастлив\w*", r"радост\w*", r"вдохнов\w*", r"высок\w*", r"сильн\w*",
]
NEGATIVE = [
    r"плох\w*", r"ужасн\w*", r"худш\w*", r"грязн\w*", r"сломан\w*", r"протека\w*",
    r"не работа\w*", r"не нрав\w*", r"разочаров\w*", r"жалоб\w*", r"безответствен\w*",
    r"груб\w*", r"хам\w*", r"уволь\w*", r"бь[её]?т\w*", r"обид\w*", r"травл\w*",
    r"не ход\w*", r"не дел\w*", r"не уме\w*", r"слаб\w*", r"посредственн\w*", r"плох\w*\s*дорог",
    r"тесн\w*", r"душн\w*", r"сыр\w*", r"холодн\w*", r"вонь", r"запах\w*", r"мусор\w*",
    r"не мы\w*", r"не убор\w*", r"беспоряд\w*", r"непонятн\w*", r"некомпетентн\w*",
    r"равнодуш\w*", r"формальн\w*", r"бездумн\w*", r"нелеп\w*", r"запуг\w*", r"предвзят\w*",
    r"отказ\w*", r"недоступн\w*", r"закон\w*", r"затрудн\w*", r"проблем\w*", r"зл\w*",
    r"сволоч\w*", r"минус\w*", r"побит\w*", r"испорч\w*", r"разбит\w*", r"трещин\w*",
    r"отсутств\w*", r"недостаточно", r"не хватает", r"некачественн\w*", r"старое\w*",
    r"устаревш\w*", r"не работает", r"сломанный", r"течёт", r"течет", r"неприятн\w*",
    r"раздража\w*", r"бесит", r"терпеть", r"невозможно", r"невозможн\w*",
]
POS_RE = [re.compile(p, re.IGNORECASE) for p in POSITIVE]
NEG_RE = [re.compile(p, re.IGNORECASE) for p in NEGATIVE]

TOKEN_RE = re.compile(r"[а-яёa-z]+")


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower().replace("ё", "е"))


def count_markers(words: list[str], regexes) -> int:
    n = 0
    for w in words:
        if any(rx.match(w) for rx in regexes):
            n += 1
    return n


def find_mentions(text: str, toks: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for topic, pats in COMPILED.items():
        pos = []
        for i, t in enumerate(toks):
            for rx in pats:
                if rx.match(t):
                    pos.append(i)
                    break
        if pos:
            out[topic] = pos
    return out


def topic_sentiment(positions: list[int], toks: list[str], all_pos: int, all_neg: int) -> str:
    """Тональность темы: окно ±6 токенов вокруг упоминаний; при равенстве — общий тон."""
    win: set[int] = set()
    for p in positions:
        win.update(range(max(0, p - 6), min(len(toks), p + 7)))
    words = [toks[i] for i in sorted(win)]
    pos = count_markers(words, POS_RE)
    neg = count_markers(words, NEG_RE)
    if pos > neg:
        return "pos"
    if neg > pos:
        return "neg"
    # равенство в окне: общий тон отзыва
    if all_pos > all_neg:
        return "pos"
    if all_neg > all_pos:
        return "neg"
    return "neutral"


def overall_tone(rating, toks: list[str]) -> str:
    if rating is not None:
        if rating <= 2:
            return "neg"
        if rating >= 4:
            return "pos"
    pos = count_markers(toks, POS_RE)
    neg = count_markers(toks, NEG_RE)
    if neg > pos:
        return "neg"
    if pos > neg:
        return "pos"
    return "neutral"


def analyze(review: dict) -> dict:
    text = review.get('text') or ''
    toks = tokens(text)
    rating = review.get('rating')
    all_pos = count_markers(toks, POS_RE)
    all_neg = count_markers(toks, NEG_RE)
    mentions = find_mentions(text, toks)
    # тема попадает в topics, если упомянута (даже с нейтральной тональностью)
    topics = {}
    for topic, positions in mentions.items():
        topics[topic] = topic_sentiment(positions, toks, all_pos, all_neg)
    return {
        'review_id': str(review['review_id']),
        'topics': topics,
        'overall': overall_tone(rating, toks),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True)
    ap.add_argument('--out', dest='out', required=True)
    args = ap.parse_args()

    raw = json.load(open(args.inp, encoding='utf-8'))
    reviews = raw['reviews'] if isinstance(raw, dict) and 'reviews' in raw else raw
    result = [analyze(r) for r in reviews]
    json.dump(result, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'Отзывов: {len(result)}, с темами: {sum(1 for r in result if r["topics"])} -> {args.out}')


if __name__ == '__main__':
    main()
