import pandas as pd

df = pd.read_excel('C:/repos/analysis-of-educational-institutions/global_data/Здания школ.xlsx', sheet_name='schools_2_stage')

print(df.head())