import pandas as pd
df_raw_nih = pd.read_csv("~/.cache/kagglehub/datasets/nih-chest-xrays/data/versions/3/Data_Entry_2017.csv")
print(df_raw_nih['View Position'].value_counts())


#--> check how much data we have in front view and side view