import pandas as pd
import json
import subprocess
import os

cred = "credentials.json"

# ── Kohorte laden ──────────────────────────────────────────────
df = pd.read_csv("data/cohort_multilabel.csv")

LABEL_COLS = [
    'covid', 'effusion', 'pneumonia', 'fibrosis', 'emphysema',
    'atelectasis', 'opacity', 'normal'
]

print(f"Gesamte Kohorte: {len(df)} Serien")
print(f"Geschätzte Gesamtgröße: {df['file_size'].sum() / 1e9:.1f} GB")

print("\n=== Label-Verteilung ===")
for col in LABEL_COLS:
    if col in df.columns:
        count = int(df[col].sum())
        pct = 100 * count / len(df)
        print(f"  {col:<20}: {count:4d} ({pct:5.1f}%)")

# ── Optional: Subset für Tests ─────────────────────────────────
DOWNLOAD_ALL = True   # False = nur kleiner Testlauf
N_PER_LABEL  = 10    # nur relevant wenn DOWNLOAD_ALL = False

if DOWNLOAD_ALL:
    df_download = df.copy()
else:
    # Balancierter Subset: N_PER_LABEL pro vorhandenem Label
    frames = []
    for col in LABEL_COLS:
        if col not in df.columns:
            continue
        pool = df[df[col] == 1]
        n = min(N_PER_LABEL, len(pool))
        if n > 0:
            frames.append(pool.sample(n=n, random_state=42))
    df_download = pd.concat(frames).drop_duplicates("object_id").reset_index(drop=True)

print(f"\nDownload-Kohorte: {len(df_download)} Serien")
print(f"Geschätzte Größe:  {df_download['file_size'].sum() / 1e9:.1f} GB")

# ── Manifest erstellen ─────────────────────────────────────────
os.makedirs("data", exist_ok=True)
manifest = [{"object_id": oid} for oid in df_download["object_id"].dropna()]
with open("data/manifest_multilabel.json", "w") as f:
    json.dump(manifest, f, indent=2)
print(f"\n✓ manifest_multilabel.json mit {len(manifest)} Einträgen")

# ── Download via gen3 CLI ──────────────────────────────────────
os.makedirs("dicom_data", exist_ok=True)

cmd = [
    "gen3", "--auth", cred,
    "--endpoint", "data.midrc.org",
    "drs-pull", "manifest", "data/manifest_multilabel.json",
    "dicom_data"   # positional, no flag
]

print("\nStarte Download...")
print(f"CMD: {' '.join(cmd)}\n")

result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("=== FEHLER ===")
    print(result.stderr)
else:
    print("✓ Download abgeschlossen")
    # Kurze Statistik was tatsächlich angekommen ist
    downloaded = [f for f in os.listdir("dicom_data") if not f.startswith(".")]
    print(f"✓ {len(downloaded)} Dateien in dicom_data/")