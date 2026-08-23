import type { SymptomTag, SymptomGroup, SymptomTopic } from "./symptoms";

// Patient history & risk-factor vocabulary grouped by topic.
// Labels must match the constants in backend/internal/patient/patient.go.
export type HistoryTag = SymptomTag;
export type HistoryGroup = SymptomGroup;
export type HistoryTopic = SymptomTopic;

export const HISTORY_TOPICS: HistoryTopic[] = [
	{
		topic: "Physical Injuries & Medical Traumas",
		groups: [
			{
				name: "Injuries & Barotrauma",
				symptoms: [
					{
						id: "injury_chest_face_sinus",
						label: "Chest, face, or sinus injuries (rib fractures, blunt trauma)",
					},
					{
						id: "penetrating_chest_injury",
						label: "Penetrating chest injury (gunshot / stab wound)",
					},
					{
						id: "barotrauma",
						label: "Barotrauma (scuba diving or flying)",
					},
					{
						id: "traumatic_pneumothorax",
						label: "Collapsed lung from pressure or trauma (pneumothorax)",
					},
				],
			},
			{
				name: "Medical / Surgical Traumas",
				symptoms: [
					{
						id: "procedural_complication",
						label:
							"Procedure complications (central lines, lung biopsy, nerve block)",
					},
					{
						id: "mechanical_ventilation",
						label: "Mechanical ventilation",
					},
					{
						id: "recent_surgery",
						label: "Recent surgery (anesthesia / open-heart)",
					},
				],
			},
		],
	},
	{
		topic: "Lifestyle Factors & Environmental Exposures",
		groups: [
			{
				name: "Smoking & Drug Use",
				symptoms: [
					{ id: "smoking_tobacco", label: "Smoking tobacco / cigarettes" },
					{ id: "cigar_marijuana", label: "Cigar or marijuana smoking" },
					{
						id: "inhaled_drug_use",
						label: "Crack cocaine smoking / inhaled drug use",
					},
					{ id: "iv_drug_use", label: "Intravenous (IV) drug use" },
				],
			},
			{
				name: "Inhalation Exposures",
				symptoms: [
					{ id: "secondhand_smoke", label: "Secondhand smoke" },
					{
						id: "dust_fumes",
						label: "Dirty air, dust, or chemical fumes (job / hobbies)",
					},
					{
						id: "wood_smoke",
						label: "Campfire or wood-burning stove smoke",
					},
					{
						id: "asbestos_silica_beryllium",
						label: "Asbestos, silica, or beryllium exposure",
					},
					{ id: "radon", label: "Elevated radon levels at home" },
					{
						id: "mold_bird_exposure",
						label: "Molds, bacteria, or bird feathers/droppings",
					},
				],
			},
			{
				name: "Physical Habits & Activity",
				symptoms: [
					{
						id: "heavy_lifting_job",
						label: "Job with heavy lifting / long hours standing",
					},
					{
						id: "sedentary",
						label: "Little to no physical activity (sedentary lifestyle)",
					},
					{
						id: "alcohol_substance",
						label: "Heavy alcohol use / substance use disorder",
					},
				],
			},
			{
				name: "Breathing Habits",
				symptoms: [
					{
						id: "shallow_breathing_pain",
						label: "Shallow breathing due to chest pain",
					},
					{
						id: "prolonged_bed_rest",
						label: "Lying flat in bed for long periods",
					},
				],
			},
		],
	},
	{
		topic: "Known Medical Conditions & History",
		groups: [
			{
				name: "Cardiovascular",
				symptoms: [
					{
						id: "heart_disease",
						label: "Heart attack or history of heart disease",
					},
					{ id: "hypertension", label: "High blood pressure (hypertension)" },
					{
						id: "cardiomyopathy",
						label: "Heart failure / weakened heart muscle (cardiomyopathy)",
					},
					{
						id: "valve_arrhythmia",
						label: "Heart valve disease or abnormal rhythm (arrhythmia)",
					},
					{
						id: "myocarditis_pericarditis",
						label: "Myocarditis or fluid around the heart",
					},
				],
			},
			{
				name: "Chronic Lung Diseases",
				symptoms: [
					{ id: "asthma_copd", label: "Asthma, COPD, or Emphysema" },
					{
						id: "pulmonary_fibrosis_ild",
						label: "Pulmonary fibrosis / interstitial lung disease",
					},
					{
						id: "prior_covid_pneumonia",
						label: "Prior Covid-19 infection or pneumonia",
					},
					{
						id: "pleural_effusion_history",
						label: "Known pleural effusion",
					},
					{
						id: "tb_recurrent_infections",
						label: "Tuberculosis or recurrent lung infections",
					},
					{
						id: "pulmonary_embolism",
						label: "Pulmonary embolism (blood clot in lungs)",
					},
					{
						id: "lung_cancer_tumors",
						label: "Lung cancer or other tumors",
					},
				],
			},
			{
				name: "Autoimmune & Inflammatory",
				symptoms: [
					{
						id: "connective_tissue_disease",
						label:
							"Connective tissue disease (rheumatoid arthritis, lupus, scleroderma)",
					},
					{
						id: "granulomatous_disease",
						label: "Granulomatous disease (sarcoidosis, LCH)",
					},
				],
			},
			{
				name: "Abdominal & Gastrointestinal",
				symptoms: [
					{
						id: "abdominal_surgery_history",
						label: "History of abdominal or pelvic surgery",
					},
					{
						id: "constipation_straining",
						label: "Chronic constipation and straining",
					},
					{
						id: "chronic_allergies",
						label: "Allergies with chronic coughing or sneezing",
					},
					{ id: "cirrhosis_liver", label: "Cirrhosis or liver disease" },
					{ id: "pancreatitis", label: "Pancreatitis" },
				],
			},
			{
				name: "Metabolic & Kidney",
				symptoms: [
					{ id: "obesity_bmi30", label: "Chronic obesity (BMI > 30)" },
					{
						id: "kidney_disease",
						label: "Nephrotic syndrome or kidney disease",
					},
				],
			},
			{
				name: "Pediatric / Congenital Risk Factors",
				symptoms: [
					{
						id: "cf_a1at_deficiency",
						label: "Cystic fibrosis / Alpha-1 antitrypsin deficiency",
					},
					{
						id: "congenital_hip_testicle",
						label: "Congenital hip dysplasia / undescended testicles",
					},
					{
						id: "marfan_connective",
						label: "Connective tissue disorder (e.g., Marfan syndrome)",
					},
				],
			},
			{
				name: "Medication & Treatment History",
				symptoms: [
					{
						id: "pneumotoxic_medication",
						label:
							"Lung-irritating medication (amiodarone, nitrofurantoin, methotrexate, cyclophosphamide)",
					},
					{ id: "radiation_therapy", label: "History of radiation therapy" },
				],
			},
		],
	},
	{
		topic: "Person-Specific Observations & Demographics",
		groups: [
			{
				name: "Demographics & Physical Traits",
				symptoms: [
					{ id: "premature_birth", label: "Premature birth status (as a child)" },
					{
						id: "pregnancy",
						label: "Pregnancy (including repeat pregnancies)",
					},
					{
						id: "tall_thin_body",
						label: "Tall, thin body type (especially in men)",
					},
				],
			},
			{
				name: "Family & Travel History",
				symptoms: [
					{
						id: "family_history_pneumo_lung",
						label: "Family history of pneumothorax or lung conditions",
					},
					{
						id: "family_history_cardiac_cancer",
						label: "Family history of heart attacks or lung cancer",
					},
					{ id: "recent_travel", label: "Recent travel history" },
				],
			},
			{
				name: "Other Observations",
				symptoms: [
					{ id: "endometriosis", label: "Endometriosis diagnosis" },
					{
						id: "psych_sequelae",
						label: "Long-term psychological effects of severe illness",
					},
					{
						id: "foreign_body",
						label: "Accidental foreign object ingestion/inhalation (food, toy parts)",
					},
				],
			},
		],
	},
];

export const ALL_HISTORY_TAGS: HistoryTag[] = HISTORY_TOPICS.flatMap(
	(t) => t.groups.flatMap((g) => g.symptoms),
);

export function historyLabelById(id: string): string | undefined {
	return ALL_HISTORY_TAGS.find((t) => t.id === id)?.label;
}
