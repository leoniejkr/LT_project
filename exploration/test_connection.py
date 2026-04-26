import pandas as pd
import os
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from gen3.query import Gen3Query
import io

api = "https://data.midrc.org"
cred = "credentials.json"  

auth = Gen3Auth(api, refresh_file=cred)
sub  = Gen3Submission(api, auth)
query = Gen3Query(auth)

# all projects
programs = sub.get_programs()
print("programs", programs)     # {'links': ['/v0/submission/Open', '/v0/submission/NCU', 
                                 #       '/v0/submission/TCIA', '/v0/submission/phs003288.c1']}

# we concentrate on Open projects
projects = sub.get_projects("Open")   # we take program Open 
print("projects", projects)


# ------------------------------------------------------------------------- #
# here: check out whats inside each program :D  --> what Nodes/Datatypes

for project in ["Open-A1", "Open-R1", "Open-A1_SCCM_VIRUS", "Open-A1_PETAL_REDCORAL"]:
    program, proj = project.split("-", 1)
    try:
        # all nodes /w count
        summary = sub.get_graphql_schema()  
        
        # export node as TSP
        result = sub.export_node(program, proj, "case", "tsv")
        df = pd.read_csv(pd.io.common.StringIO(result), sep="\t")
        print(f"\n=== {project} ===")
        print(f"Cases: {len(df)}")
        print(df.columns.tolist())
    except Exception as e:
        print(f"{project}: {e}")


# Pull the nodes that actually have findings
report_raw = sub.export_node("Open", "A1", "radiology_report", "tsv")
annot_raw  = sub.export_node("Open", "A1", "annotation", "tsv")
cond_raw   = sub.export_node("Open", "A1", "condition", "tsv")
obs_raw    = sub.export_node("Open", "A1", "observation", "tsv")

df_report = pd.read_csv(io.StringIO(report_raw), sep="\t")
df_annot  = pd.read_csv(io.StringIO(annot_raw),  sep="\t")
df_cond   = pd.read_csv(io.StringIO(cond_raw),   sep="\t")
df_obs    = pd.read_csv(io.StringIO(obs_raw),    sep="\t")

# See what's in there
print(df_report.columns.tolist())
print(df_annot.columns.tolist())
print(df_cond.columns.tolist())
print(df_obs.columns.tolist())

print(df_obs["observation_name"].value_counts().head(20))
print(df_obs["observation_answer"].value_counts().head(20))

# And a sample of values
print(df_report.head(3))
print(df_cond["condition_name"].value_counts().head(20) if "condition_name" in df_cond.columns else df_cond.head(3))