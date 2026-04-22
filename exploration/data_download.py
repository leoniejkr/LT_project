import pandas as pd
import json
import subprocess
import os

cred = "credentials.json"  # pfad zu deinen MIDRC credentials

# ------------------------------------------------------------------ #
# Kleine Testkohorte aus cohort_balanced.csv laden
# (falls du das noch nicht hast, N=50 pro Klasse reicht zum Testen)
# ------------------------------------------------------------------ #
df = pd.read_csv("data/cohort_balanced.csv")


n = int(len(df)/2)  # für balanced data
# n = 10 # für kleinen test


df_small = pd.concat([
    df[df["covid19_positive"] == "Yes"].sample(n=n, random_state=42),
    df[df["covid19_positive"] == "No"].sample(n=n, random_state=42)
]).reset_index(drop=True)

print(f"Download-Kohorte: {len(df_small)} Serien")
print(f"Geschätzte Größe: {df_small['file_size'].sum() / 1e9:.1f} GB")

# ------------------------------------------------------------------ #
# Manifest erstellen
# ------------------------------------------------------------------ #
manifest = [{"object_id": oid} for oid in df_small["object_id"].dropna()]
with open("data/manifest_balanced.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"✓ manifest_balanced.json mit {len(manifest)} Einträgen")

# ------------------------------------------------------------------ #
# Download via gen3 CLI
# ------------------------------------------------------------------ #
os.makedirs("dicom_data", exist_ok=True)
os.chdir("dicom_data")

cmd = [
    "gen3", "--auth", f"../{cred}",
    "--endpoint", "data.midrc.org",
    "drs-pull", "manifest", "../data/manifest_balanced.json"
]

print("\nStarte Download...")
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("Errors:", result.stderr)