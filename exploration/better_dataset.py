import io
import os
import sys
import pandas as pd
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

# Configuration
API = "https://data.midrc.org"
PROGRAM = "Open"  # MIDRC nutzt meistens "Open" als Programm

print("=" * 80)
print("MIDRC RSNA & Kontrollgruppen Explorer")
print("=" * 80)

# 1. Authentifizierung
try:
    auth = Gen3Auth(API, refresh_file="credentials.json")
    sub = Gen3Submission(API, auth)
    print(f"[✓] Verbunden mit {API}")
except Exception as e:
    print(f"[X] Fehler bei der Authentifizierung: {e}")
    sys.exit(1)

# 2. Verfügbare Projekte auflisten (Via GraphQL)
print("\n[1] Rufe verfügbare Projekte ab...")
try:
    # Wir nutzen eine saubere GraphQL Query, um alle registrierten Projekte abzufragen
    query_string = """
    {
      project (first: 100) {
        code
      }
    }
    """
    query_res = sub.query(query_string)
    
    if "data" in query_res and "project" in query_res["data"]:
        project_ids = [p["code"] for p in query_res["data"]["project"]]
    else:
        # Fallback falls die Struktur unerwartet ist
        print("[!] Unerwartete GraphQL-Struktur, nutze Hardcoded Fallback-Liste.")
        project_ids = ["A1", "R1", "RICORD", "TCIA"]
        
    print(f"Gefundene Projekte im System: {project_ids}")
except Exception as e:
    print(f"[!] GraphQL Abfrage fehlgeschlagen ({e}). Nutze Standard-MIDRC-Projektliste.")
    # Absolut sicherer Fallback mit den bekanntesten MIDRC-Projekten
    project_ids = ["A1", "R1", "RICORD"]

# Wir fokussieren uns auf RSNA/ACR Kohorten (enthalten oft 'R' oder 'A')
target_projects = [pid for pid in project_ids if "R" in pid or "A" in pid or "RICORD" in pid]
# Falls der Filter leer läuft, nehmen wir einfach alle gefundenen IDs
if not target_projects:
    target_projects = project_ids

print(f"Fokussiere Untersuchung auf folgende Projekte: {target_projects}")

# 3. LOINC Filter Definitionen (für Lungenregion)
CT_CHEST_LOINC = {
    "CT Chest WO contrast", 
    "CT Chest W contrast IV", 
    "CTA Pulmonary arteries for pulmonary embolus W contrast IV", 
    "CTA Chest vessels W contrast IV",
    "CT Chest and Abdomen and Pelvis W contrast IV",
    "CT Chest and Abdomen and Pelvis WO contrast"
}
CXR_CHEST_LOINC = {
    "XR Chest AP", 
    "XR Chest PA", 
    "XR Chest AP and Lateral",
    "XR Chest PA and Lateral",
    "XR Chest AP portable", 
    "XR Chest 2 views", 
    "Portable XR Chest AP", 
    "XR Chest"
}

def clean_id(s):
    return str(s).replace("[","").replace("]","").replace("'","").replace('"',"").strip()

# 4. Schleife über die Projekte zur Analyse
print("\n[2] Analysiere Projekt-Strukturen...")
for proj in target_projects:
    print(f"\n--- Analyse für Projekt: {PROGRAM}-{proj} ---")
    try:
        # Exportiere die Kernknoten für dieses spezifische Projekt
        cases_raw = sub.export_node(PROGRAM, proj, "case", "tsv")
        cond_raw = sub.export_node(PROGRAM, proj, "condition", "tsv")
        study_raw = sub.export_node(PROGRAM, proj, "imaging_study", "tsv")
        
        df_cases = pd.read_csv(io.StringIO(cases_raw), sep="\t")
        df_cond = pd.read_csv(io.StringIO(cond_raw), sep="\t")
        df_study = pd.read_csv(io.StringIO(study_raw), sep="\t")
        
        total_cases = len(df_cases)
        if total_cases == 0:
            print("   Keine Cases in diesem Projekt gefunden.")
            continue
            
        # COVID-19 Filter basierend auf Conditions
        covid_terms = ["COVID-19", "U07.1", "coronavirus", "SARS-associated"]
        is_covid = df_cond["concept_name"].str.contains('|'.join(covid_terms), case=False, na=False)
        covid_case_ids = set(df_cond[is_covid]["case_id"].apply(clean_id))
        
        all_case_ids = set(df_cases["submitter_id"].apply(clean_id))
        control_case_ids = all_case_ids - covid_case_ids
        
        # Lungen/Chest Filter via LOINC
        df_study["case_ids_clean"] = df_study["case_ids"].apply(clean_id)
        df_chest = df_study[df_study["loinc_long_common_name"].isin(CT_CHEST_LOINC | CXR_CHEST_LOINC)]
        chest_case_ids = set(df_chest["case_ids_clean"])
        
        # Schnittmengen berechnen
        chest_controls = control_case_ids.intersection(chest_case_ids)
        chest_covid = covid_case_ids.intersection(chest_case_ids)
        
        print(f"   Gesamt-Cases (Patienten): {total_cases:,}")
        print(f"   Davon COVID-positiv:      {len(covid_case_ids):,}")
        print(f"   Davon COVID-negativ:      {len(control_case_ids):,}")
        print(f"   [Lunge] Chest-Studien gesamt: {len(df_chest):,}")
        print(f"   [Lunge] Chest-Studien von COVID-NEGATIVEN Patienten: {len(chest_controls):,}")
        print(f"   [Lunge] Chest-Studien von COVID-POSITIVEN Patienten: {len(chest_covid):,}")
        
    except Exception as e:
        print(f"   Konnte Projekt {proj} nicht vollständig analysieren (Evtl. Knoten leer): {e}")

print("\n" + "=" * 80)
print("Exploration abgeschlossen.")
print("=" * 80)