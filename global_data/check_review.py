import json

with open('C:/repos/analysis-of-educational-institutions/global_data/compare_review.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

reviews = data['reviews']

all_reviews_text = []

for review in reviews:
    review_text = f'{review['text']} || '
    all_reviews_text.append(review_text)

with open('C:/repos/analysis-of-educational-institutions/global_data/all_reviews_text.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(all_reviews_text))

print(all_reviews_text)