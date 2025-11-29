import os
import json

def recognize_review(file_path):

    with open(file_path, "r", encoding='utf-8') as f:
        review_data = json.load(f)

    for review_info in (review_data['reviews']):
        review_info_text = review_info['text']
        review_info_date = review_info['date']
        print(review_info_text, review_info_date)


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(RM_ROOT, 'rm_data')
INPUT_DIR = os.path.join(DATA_DIR, 'rm_input')
INPUT_REVIEW_FILE = os.path.join(INPUT_DIR, 'rm_input_test_data.json')

recognize_review(INPUT_REVIEW_FILE)