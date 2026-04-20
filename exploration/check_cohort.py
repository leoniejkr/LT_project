import pandas as pd

df = pd.read_csv("data/cohort_metadata.csv")

print(f"Gesamt Serien: {len(df)}")
print(f"\nCOVID Status:")
print(df["covid19_positive"].value_counts())
print(f"\nGeschlecht:")
print(df["sex"].value_counts())
print(f"\nAlter (Durchschnitt): {df['age_at_index'].mean():.1f}")
print(f"\nICU Fälle: {df['icu_indicator'].sum()}")
print(f"\nSeries Descriptions (Top 20):")
print(df["series_description"].value_counts().head(20))
print(f"\nDateigröße total (GB): {df['file_size'].sum() / 1e9:.1f}")