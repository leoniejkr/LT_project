import pandas as pd
import io, json
from collections import Counter
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

api  = "https://data.midrc.org"
auth = Gen3Auth(api, refresh_file="credentials.json")
sub  = Gen3Submission(api, auth)

# ----------------------------
# Load relevant nodes
# ----------------------------
print("=" * 80)
print("LOADING NODES FROM GEN3...")
print("=" * 80)

obs_raw   = sub.export_node("Open", "A1", "observation", "tsv")
proc_raw  = sub.export_node("Open", "A1", "procedure", "tsv")
visit_raw = sub.export_node("Open", "A1", "visit", "tsv")
annot_raw = sub.export_node("Open", "A1", "annotation", "tsv")

df_obs   = pd.read_csv(io.StringIO(obs_raw), sep="\t", low_memory=False)
df_proc  = pd.read_csv(io.StringIO(proc_raw), sep="\t", low_memory=False)
df_visit = pd.read_csv(io.StringIO(visit_raw), sep="\t", low_memory=False)
df_annot = pd.read_csv(io.StringIO(annot_raw), sep="\t", low_memory=False)

# ----------------------------
# EXAMINE RAW NODES
# ----------------------------
print("\n" + "─" * 80)
print("OBSERVATION NODE")
print("─" * 80)
print(f"Shape: {df_obs.shape}")
print(f"Columns: {list(df_obs.columns)}")
print(f"\nFirst rows:\n{df_obs.head()}")
if len(df_obs) > 0:
    print(f"\nUnique observation_name values (first 20):\n{df_obs['observation_name'].value_counts().head(20)}")
else:
    print("⚠️  OBSERVATION NODE IS EMPTY!")

print("\n" + "─" * 80)
print("PROCEDURE NODE")
print("─" * 80)
print(f"Shape: {df_proc.shape}")
print(f"Columns: {list(df_proc.columns)}")
print(f"\nFirst rows:\n{df_proc.head()}")
if len(df_proc) > 0:
    print(f"\nUnique procedure_name values (first 20):\n{df_proc['procedure_name'].value_counts().head(20)}")

print("\n" + "─" * 80)
print("VISIT NODE")
print("─" * 80)
print(f"Shape: {df_visit.shape}")
print(f"Columns: {list(df_visit.columns)}")
print(f"\nFirst rows:\n{df_visit.head()}")
if len(df_visit) > 0 and "visit_type" in df_visit.columns:
    print(f"\nUnique visit_type values:\n{df_visit['visit_type'].value_counts()}")

print("\n" + "─" * 80)
print("ANNOTATION NODE")
print("─" * 80)
print(f"Shape: {df_annot.shape}")
print(f"Columns: {list(df_annot.columns)}")
print(f"\nFirst rows:\n{df_annot.head()}")
if len(df_annot) > 0:
    print(f"\nUnique values in mRALE columns:")
    for col in df_annot.columns:
        if 'mRALE' in col or 'score' in col:
            print(f"  {col}: {df_annot[col].value_counts().head()}")

