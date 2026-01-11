import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
PROJECT_ROOT = os.path.dirname(DB_ROOT)
EXCEL_FILE = os.path.join(PROJECT_ROOT, "global_data", "Здания школ.xlsx")

df = pd.read_excel(EXCEL_FILE, sheet_name='schools_2_stage')

print(df.head())