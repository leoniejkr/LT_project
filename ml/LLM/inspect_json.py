import glob
import json
import os
import pandas as pd


# -------------------------------------------------------------------------
# 1. HELPER FUNCTIONS
# -------------------------------------------------------------------------
def infer_demographic(name):
    """Detect target demographic based on sub-condition name."""
    name_lower = str(name).lower()
    if any(
        k in name_lower
        for k in ["child", "pediatric", "kid", "infant", "baby", "babies"]
    ):
        return "Pediatric"
    elif any(
        k in name_lower for k in ["pregnan", "maternal", "fetal", "postpartum"]
    ):
        return "Pregnancy"
    elif any(k in name_lower for k in ["elderly", "geriatric", "aging"]):
        return "Geriatric"
    return "General"


def to_string_list(val):
    """Converts lists or objects to clean semicolon-separated strings for CSV compatibility."""
    if isinstance(val, list):
        return "; ".join([str(v) for v in val if v])
    elif pd.isna(val) or val is None:
        return "N/A"
    return str(val)


# -------------------------------------------------------------------------
# 2. MAIN EXTRACTION PIPELINE WITH FILE TRACKING
# -------------------------------------------------------------------------
def extract_and_flatten_disease_data(json_file_paths):
    flat_records = []

    # Dictionaries to track which files contain specific keys
    top_key_locations = {}
    subtype_key_locations = {}

    # Standardized key baselines
    known_top_keys = {
        "primary_condition",
        "disease_name",
        "definition",
        "is_contagious",
        "general_symptoms",
        "symptoms",
        "general_causes",
        "causes",
        "transmission_causes",
        "general_treatments",
        "treatments",
        "general_diagnosis_methods",
        "diagnosis_methods",
        "diagnosis",
        "general_outlook",
        "outlook",
        "general_prevention",
        "prevention",
        "complications",
        "life_expectancy",
        "living_with",
        "risk_factors",
        "lifestyle_risk_factors",
        "manifestations_and_subtypes",
        "types_and_subtypes",
        "subtypes_and_causes",
        "underlying_causes_and_conditions",
        "underlying_causes_and_treatments",
        "categories",
        "related_conditions",
        "related_and_underlying_conditions",
        "causes_by_type",
        "structural_classification",
        "causes_by_category",
        "causes_by_etiology",
        "causes_by_etiology_and_subtypes",
        "etiology_and_subtypes",
        "classification_types",
        "differential_diagnosis",
        "demographic_manifestations",
    }

    known_subtype_keys = {
        "subtype_name",
        "type_name",
        "type",
        "cause_name",
        "category_name",
        "category",
        "definition",
        "mechanism",
        "description",
        "symptoms",
        "specific_symptoms",
        "cause_specific_symptoms",
        "causes",
        "sub_causes",
        "diagnosis",
        "treatments",
        "specific_treatments",
        "targeted_treatments",
        "targeted_treatment",
        "complications",
        "associated_complications",
        "outlook",
        "living_with",
        "prevention",
        "examples",
        "triggers",
        "associated_groups_or_conditions",
        "notes",
        "categories",
        "related_conditions",
        "types",
        "subtypes",
        "specific_subtypes",
        "locations",
        "location_name",
        "specific_variant",
        "variant_name",
        "relationship",
        "details",
        "disease_name",
        "condition",
        "is_contagious",
        "life_expectancy",
    }

    for file_path in json_file_paths:
        file_name = os.path.basename(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"⚠️ Error loading {file_path}: {e}")
                continue

            if isinstance(data, dict):
                data = [data]

            for item in data:
                # Track top-level keys and their source files
                for k in item.keys():
                    top_key_locations.setdefault(k, set()).add(file_name)

                parent_name = item.get("primary_condition") or item.get(
                    "disease_name", "Unknown Condition"
                )
                parent_def = item.get("definition", "N/A")
                is_contagious = item.get("is_contagious", None)

                # Standardized core lists with fallbacks & additions
                general_symptoms = item.get("general_symptoms") or item.get(
                    "symptoms", []
                )

                general_causes = (
                    item.get("general_causes")
                    or item.get("causes", [])
                    + item.get("transmission_causes", [])
                )

                general_treatments = item.get("general_treatments") or item.get(
                    "treatments", []
                )
                general_diagnosis = (
                    item.get("general_diagnosis_methods")
                    or item.get("diagnosis_methods")
                    or item.get("diagnosis", [])
                )
                general_outlook = item.get("general_outlook") or item.get(
                    "outlook", []
                )
                general_prevention = item.get("general_prevention") or item.get(
                    "prevention", []
                )
                complications = item.get("complications", [])
                life_expectancy = item.get("life_expectancy", [])
                living_with = item.get("living_with", [])

                risk_factors = item.get("risk_factors", []) + item.get(
                    "lifestyle_risk_factors", []
                )

                categories = item.get("categories", [])
                related_conditions = item.get("related_conditions", [])

                # 1. Add Parent Entry
                parent_record = {
                    "entity_type": "primary",
                    "primary_condition": parent_name,
                    "condition_name": parent_name,
                    "target_demographic": "General",
                    "definition": parent_def,
                    "symptoms": general_symptoms,
                    "causes": general_causes,
                    "diagnosis": general_diagnosis,
                    "treatments": general_treatments,
                    "complications": complications,
                    "outlook": general_outlook,
                    "life_expectancy": life_expectancy,
                    "prevention": general_prevention,
                    "living_with": living_with,
                    "risk_factors": risk_factors,
                    "categories": categories,
                    "related_conditions": related_conditions,
                    "is_contagious": is_contagious,
                }
                flat_records.append(parent_record)

                # 2. Consolidate ALL subtype, classification, and etiology arrays
                raw_subtypes = (
                    item.get("manifestations_and_subtypes", [])
                    + item.get("types_and_subtypes", [])
                    + item.get("subtypes_and_causes", [])
                    + item.get("causes_by_type", [])
                    + item.get("structural_classification", [])
                    + item.get("causes_by_category", [])
                    + item.get("causes_by_etiology", [])
                    + item.get("causes_by_etiology_and_subtypes", [])
                    + item.get("etiology_and_subtypes", [])
                    + item.get("classification_types", [])
                    + item.get("demographic_manifestations", [])
                )

                for sub in raw_subtypes:
                    for sk in sub.keys():
                        subtype_key_locations.setdefault(sk, set()).add(
                            file_name
                        )

                    sub_name = (
                        sub.get("subtype_name")
                        or sub.get("type_name")
                        or sub.get("category_name")
                        or sub.get("category")
                        or sub.get("type")
                        or sub.get("cause_name")
                        or f"{parent_name} Subtype"
                    )

                    sub_symptoms = (
                        sub.get("specific_symptoms")
                        or sub.get("cause_specific_symptoms")
                        or sub.get("symptoms")
                        or general_symptoms
                    )

                    sub_treatments = (
                        sub.get("specific_treatments")
                        or sub.get("targeted_treatments")
                        or sub.get("targeted_treatment")
                        or sub.get("treatments")
                        or general_treatments
                    )

                    sub_causes = (
                        sub.get("causes")
                        or sub.get("sub_causes")
                        or sub.get("types")
                        or [sub.get("details")]
                        if sub.get("details")
                        else general_causes
                    )

                    sub_complications = sub.get("complications", complications)
                    sub_outlook = sub.get("outlook", general_outlook)
                    sub_living = sub.get("living_with", living_with)
                    sub_prevention = sub.get("prevention", general_prevention)

                    sub_def = (
                        sub.get("definition")
                        or sub.get("description")
                        or sub.get("mechanism")
                        or f"A subtype, category, or etiology of {parent_name}."
                    )

                    flat_records.append(
                        {
                            "entity_type": "subtype",
                            "primary_condition": parent_name,
                            "condition_name": sub_name,
                            "target_demographic": infer_demographic(sub_name),
                            "definition": sub_def,
                            "symptoms": sub_symptoms,
                            "causes": sub_causes,
                            "diagnosis": sub.get(
                                "diagnosis", general_diagnosis
                            ),
                            "treatments": sub_treatments,
                            "complications": sub_complications,
                            "outlook": sub_outlook,
                            "life_expectancy": sub.get(
                                "life_expectancy", life_expectancy
                            ),
                            "prevention": sub_prevention,
                            "living_with": sub_living,
                            "risk_factors": risk_factors,
                            "categories": categories,
                            "related_conditions": related_conditions,
                            "is_contagious": sub.get(
                                "is_contagious", is_contagious
                            ),
                        }
                    )

                    # Extract nested items inside classification_types / causes_by_category (types, subtypes, locations, specific_subtypes, categories)
                    nested_subtypes = (
                        sub.get("types", [])
                        + sub.get("subtypes", [])
                        + sub.get("specific_subtypes", [])
                        + sub.get("locations", [])
                        + sub.get("categories", [])
                    )

                    for n_sub in nested_subtypes:
                        if isinstance(n_sub, dict):
                            for nsk in n_sub.keys():
                                subtype_key_locations.setdefault(
                                    nsk, set()
                                ).add(file_name)

                            n_name = (
                                n_sub.get("subtype_name")
                                or n_sub.get("type_name")
                                or n_sub.get("category_name")
                                or n_sub.get("location_name")
                                or n_sub.get("cause_name")
                                or f"{sub_name} Subtype"
                            )

                            n_def = (
                                n_sub.get("definition")
                                or n_sub.get("details")
                                or f"A specific form under {sub_name}."
                            )

                            flat_records.append(
                                {
                                    "entity_type": "subtype",
                                    "primary_condition": parent_name,
                                    "condition_name": f"{n_name} ({sub_name})",
                                    "target_demographic": infer_demographic(
                                        n_name
                                    ),
                                    "definition": n_def,
                                    "symptoms": n_sub.get(
                                        "specific_symptoms", sub_symptoms
                                    ),
                                    "causes": n_sub.get("causes", sub_causes),
                                    "diagnosis": general_diagnosis,
                                    "treatments": n_sub.get(
                                        "specific_treatments", sub_treatments
                                    ),
                                    "complications": n_sub.get(
                                        "complications", sub_complications
                                    ),
                                    "outlook": n_sub.get(
                                        "outlook", sub_outlook
                                    ),
                                    "life_expectancy": life_expectancy,
                                    "prevention": sub_prevention,
                                    "living_with": sub_living,
                                    "risk_factors": risk_factors,
                                    "categories": categories,
                                    "related_conditions": related_conditions,
                                    "is_contagious": is_contagious,
                                }
                            )

                            # Deep extraction for variants inside types
                            variant = n_sub.get("specific_variant")
                            if isinstance(variant, dict):
                                for vsk in variant.keys():
                                    subtype_key_locations.setdefault(
                                        vsk, set()
                                    ).add(file_name)
                                v_name = variant.get(
                                    "variant_name", f"{n_name} Variant"
                                )
                                flat_records.append(
                                    {
                                        "entity_type": "subtype",
                                        "primary_condition": parent_name,
                                        "condition_name": f"{v_name} ({n_name})",
                                        "target_demographic": infer_demographic(
                                            v_name
                                        ),
                                        "definition": variant.get(
                                            "definition", ""
                                        ),
                                        "symptoms": sub_symptoms,
                                        "causes": sub_causes,
                                        "diagnosis": general_diagnosis,
                                        "treatments": sub_treatments,
                                        "complications": sub_complications,
                                        "outlook": sub_outlook,
                                        "life_expectancy": life_expectancy,
                                        "prevention": sub_prevention,
                                        "living_with": sub_living,
                                        "risk_factors": risk_factors,
                                        "categories": categories,
                                        "related_conditions": related_conditions,
                                        "is_contagious": is_contagious,
                                    }
                                )

                # 3. Extract Underlying Causes / Related Conditions
                underlying = (
                    item.get("underlying_causes_and_conditions", [])
                    + item.get("underlying_causes_and_treatments", [])
                    + item.get("related_and_underlying_conditions", [])
                )
                for u in underlying:
                    for uk in u.keys():
                        subtype_key_locations.setdefault(uk, set()).add(
                            file_name
                        )

                    u_name = (
                        u.get("cause_name")
                        or u.get("disease_name")
                        or u.get("condition")
                        or "Underlying Cause"
                    )
                    u_desc = (
                        u.get("description")
                        or u.get("mechanism")
                        or u.get("relationship")
                        or ""
                    )
                    flat_records.append(
                        {
                            "entity_type": "underlying_cause",
                            "primary_condition": parent_name,
                            "condition_name": f"{u_name} causing {parent_name}",
                            "target_demographic": "General",
                            "definition": u_desc,
                            "symptoms": u.get("cause_specific_symptoms", []),
                            "causes": u.get(
                                "sub_causes", u.get("examples", [u_name])
                            ),
                            "diagnosis": general_diagnosis,
                            "treatments": u.get(
                                "targeted_treatment", general_treatments
                            ),
                            "complications": u.get(
                                "complications",
                                u.get(
                                    "associated_complications", complications
                                ),
                            ),
                            "outlook": u.get("outlook", general_outlook),
                            "life_expectancy": life_expectancy,
                            "prevention": general_prevention,
                            "living_with": living_with,
                            "risk_factors": risk_factors,
                            "categories": categories,
                            "related_conditions": related_conditions,
                            "is_contagious": is_contagious,
                        }
                    )

                # 4. Extract Differential Diagnosis
                diff_diag = item.get("differential_diagnosis")
                if isinstance(diff_diag, dict):
                    diff_name = diff_diag.get(
                        "condition", "Differential Diagnosis"
                    )
                    diff_desc = diff_diag.get("key_difference", "")
                    diff_causes = diff_diag.get("overlapping_causes", [])

                    flat_records.append(
                        {
                            "entity_type": "differential_diagnosis",
                            "primary_condition": parent_name,
                            "condition_name": f"Differential Diagnosis: {diff_name} vs {parent_name}",
                            "target_demographic": "General",
                            "definition": f"Key Difference: {diff_desc}",
                            "symptoms": general_symptoms,
                            "causes": diff_causes,
                            "diagnosis": general_diagnosis,
                            "treatments": general_treatments,
                            "complications": complications,
                            "outlook": general_outlook,
                            "life_expectancy": life_expectancy,
                            "prevention": general_prevention,
                            "living_with": living_with,
                            "risk_factors": risk_factors,
                            "categories": categories,
                            "related_conditions": related_conditions,
                            "is_contagious": is_contagious,
                        }
                    )

    # Compute unmapped keys
    unrecognized_top = set(top_key_locations.keys()) - known_top_keys
    unrecognized_sub = set(subtype_key_locations.keys()) - known_subtype_keys

    return (
        flat_records,
        top_key_locations,
        unrecognized_top,
        subtype_key_locations,
        unrecognized_sub,
    )


# -------------------------------------------------------------------------
# 3. JSONL GENERATOR
# -------------------------------------------------------------------------
def build_jsonl_fine_tuning(flat_records, output_jsonl_path):
    jsonl_data = []

    for entry in flat_records:
        cond_name = entry["condition_name"]
        parent = entry["primary_condition"]

        symptoms = to_string_list(entry["symptoms"])
        treatments = to_string_list(entry["treatments"])
        causes = to_string_list(entry["causes"])
        diagnosis = to_string_list(entry["diagnosis"])
        complications = to_string_list(entry["complications"])
        outlook = to_string_list(entry["outlook"])
        living_with = to_string_list(entry["living_with"])

        user_prompt = f"Provide a complete clinical overview and management guide for {cond_name}."
        assistant_resp = (
            f"**Condition:** {cond_name}\n"
            f"**Category:** {parent}\n"
            f"**Definition:** {entry['definition']}\n\n"
            f"**Symptoms:** {symptoms}\n\n"
            f"**Causes:** {causes}\n\n"
            f"**Diagnosis:** {diagnosis}\n\n"
            f"**Treatments:** {treatments}\n\n"
            f"**Complications:** {complications}\n\n"
            f"**Outlook:** {outlook}\n\n"
            f"**Living With & Management:** {living_with}"
        )

        jsonl_data.append(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a clinical reference model trained on structured medical data.",
                    },
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": assistant_resp},
                ]
            }
        )

    with open(output_jsonl_path, "w", encoding="utf-8") as f:
        for line in jsonl_data:
            f.write(json.dumps(line) + "\n")


# -------------------------------------------------------------------------
# 4. EXECUTION & LOCATION REPORT
# -------------------------------------------------------------------------
if __name__ == "__main__":
    json_files = glob.glob("ml/LLM/files/raw_data/*.json")
    print(f"🔍 Found {len(json_files)} JSON file(s) to process.")

    if not json_files:
        print("❌ No JSON files found in current directory!")
    else:
        (
            records,
            top_locs,
            unrec_top,
            sub_locs,
            unrec_sub,
        ) = extract_and_flatten_disease_data(json_files)

        df = pd.DataFrame(records)

        # Explicit header order
        header_order = [
            "entity_type",
            "primary_condition",
            "condition_name",
            "target_demographic",
            "definition",
            "symptoms",
            "causes",
            "diagnosis",
            "treatments",
            "complications",
            "outlook",
            "life_expectancy",
            "prevention",
            "living_with",
            "risk_factors",
            "categories",
            "related_conditions",
            "is_contagious",
        ]

        existing_cols = [c for c in header_order if c in df.columns]
        df = df[existing_cols]

        list_columns = [
            "symptoms",
            "causes",
            "diagnosis",
            "treatments",
            "complications",
            "outlook",
            "life_expectancy",
            "prevention",
            "living_with",
            "risk_factors",
            "categories",
            "related_conditions",
        ]
        for col in list_columns:
            if col in df.columns:
                df[col] = df[col].apply(to_string_list)

        df.to_csv("ml/LLM/files/medical_dataset_flattened.csv", index=False)
        build_jsonl_fine_tuning(records, "ml/LLM/files/fine_tuning_ready.jsonl")

        # AUDIT REPORT WITH FILE LOCATIONS
        print("\n" + "=" * 65)
        print("              DATASET VERIFICATION & FILE LOCATION AUDIT             ")
        print("=" * 65)
        print(f"✅ Total rows generated in CSV: {len(df)}")
        print(f"📄 Saved CSV to: 'ml/LLM/files/medical_dataset_flattened.csv'")
        print(f"📄 Saved JSONL to: 'ml/LLM/files/fine_tuning_ready.jsonl'\n")

        if unrec_top:
            print("⚠️ UNRECOGNIZED TOP-LEVEL KEYS & THEIR SOURCE FILES:")
            for k in sorted(list(unrec_top)):
                files_str = ", ".join(sorted(list(top_locs[k])))
                print(f"   - '{k}' -> found in: [{files_str}]")
        else:
            print("✅ All top-level keys are fully mapped!")

        if unrec_sub:
            print("\n⚠️ UNRECOGNIZED SUBTYPE KEYS & THEIR SOURCE FILES:")
            for k in sorted(list(unrec_sub)):
                files_str = ", ".join(sorted(list(sub_locs[k])))
                print(f"   - '{k}' -> found in: [{files_str}]")
        else:
            print("\n✅ All inner subtype keys are fully mapped!")

        print("\n" + "=" * 65)
