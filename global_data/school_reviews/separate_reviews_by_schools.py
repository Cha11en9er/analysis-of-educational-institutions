import json

def write_reviews_to_file(reviews, file_name):
    with open(f'C:/repos/analysis-of-educational-institutions/global_data/school_reviews/school_reviews_separately/school_reviews_separately_{file_name}.json', 'w', encoding='utf-8') as f:
        json.dump(reviews, f, ensure_ascii=False, indent=4)

with open('C:/repos/analysis-of-educational-institutions/global_data/school_reviews/compare_review_clear.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

reviews = data['reviews']

school_ids = set()

for review in reviews:
    school_id = review['school_id']
    school_ids.add(school_id)

for school_id in school_ids:
    school_reviews = [review for review in reviews if review['school_id'] == school_id]
    write_reviews_to_file(school_reviews, school_id)

print(school_ids)