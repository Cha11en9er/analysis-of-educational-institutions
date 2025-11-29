import json
import os

def make_count_of_reviews_input_file_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        school_data = json.load(f)

    input_file_data = {}

    for i in range(len(school_data["data"])):
        input_file_data[school_data["data"][i]["id"]] = school_data["data"][i]["reviews_count"]

    return input_file_data

def make_count_of_reviews_output_file_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        review_data = json.load(f)

    output_file_data = {}
    
    for i in range(len(review_data["reviews"])):
        school_id = review_data["reviews"][i]["school_id"]
        if school_id not in output_file_data:
            output_file_data[school_id] = 0
        output_file_data[school_id] += 1

    return output_file_data

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
YM_ROOT = os.path.dirname(CURRENT_DIR)
DATA_DIR = os.path.join(YM_ROOT, "ym_data", "ym_review_data")
INPUT_DIR = os.path.join(DATA_DIR, "input")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
INPUT_SCHOOL_FILE = os.path.join(INPUT_DIR, "ym_gold_all_school_data.json")
INPUT_REVIEW_FILE = os.path.join(OUTPUT_DIR, "ym_review_output.json")

input_file_data = make_count_of_reviews_input_file_data(INPUT_SCHOOL_FILE)
output_file_data = make_count_of_reviews_output_file_data(INPUT_REVIEW_FILE)
print(input_file_data)
print(60 * "-")
print(output_file_data)