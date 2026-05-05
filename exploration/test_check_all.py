import pandas as pd
import io, json
from collections import Counter
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission

api  = "https://data.midrc.org"
auth = Gen3Auth(api, refresh_file="credentials.json")
sub  = Gen3Submission(api, auth)

# check all available nodes in program
schema = sub.get_graphql_schema()

print(schema.keys())  # shows all node names



import json

schema = sub.get_graphql_schema()

types = schema["data"]["__schema"]["types"]

node_names = [t["name"] for t in types if "name" in t]

print(node_names[:50])

data_nodes = [
    t["name"]
    for t in types
    if t.get("kind") == "OBJECT"
]

print(data_nodes)