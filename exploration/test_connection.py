import pandas as pd
import os
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from gen3.query import Gen3Query

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