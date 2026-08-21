export interface SymptomTag {
	id: string;
	label: string;
	description?: string;
}

export interface SymptomGroup {
	name?: string;
	symptoms: SymptomTag[];
}

export interface SymptomTopic {
	topic: string;
	groups: SymptomGroup[];
}

export const SYMPTOM_TOPICS: SymptomTopic[] = [
	{
		topic: "Breathing & Respiratory Symptoms",
		groups: [
			{
				name: "Atelectasis / Collapse Signs",
				symptoms: [
					{ id: "apnea", label: "Pauses in breathing", description: "apnea" },
					{ id: "grunting", label: "Grunting" },
					{
						id: "shallow_breathing",
						label: "Shallow breathing",
						description: "breathing in short, shallow spurts",
					},
				],
			},
			{
				name: "Breathing Difficulty / Dyspnea",
				symptoms: [
					{
						id: "dyspnea",
						label: "Shortness of breath",
						description:
							"dyspnea, especially on exertion or when lying flat",
					},
					{ id: "catching_breath", label: "Difficulty catching breath" },
					{
						id: "deep_breath_difficulty",
						label: "Inability to take a deep breath",
					},
					{
						id: "air_hunger",
						label: "Constant feeling of not getting enough air",
					},
					{
						id: "suffocation",
						label: "Feeling like suffocating / gasping for air",
					},
					{
						id: "nocturnal_dyspnea",
						label: "Breathlessness that awakens you from sleep",
					},
					{
						id: "orthopnea",
						label: "Orthopnea",
						description:
							"difficulty breathing unless sitting or standing upright",
					},
				],
			},
			{
				name: "Breathing Rate & Effort",
				symptoms: [
					{
						id: "tachypnea",
						label: "Rapid breathing",
						description: "faster breathing, tachypnea",
					},
					{
						id: "retractions",
						label: "Increased work of breathing",
						description: "retractions",
					},
				],
			},
			{
				name: "Breathing Sounds",
				symptoms: [
					{ id: "wheezing", label: "Wheezing" },
					{ id: "stridor", label: "Stridor" },
					{
						id: "crepitus",
						label: "Crepitus",
						description: "crackling sound under the skin",
					},
					{
						id: "rales_rhonchi",
						label: "Rattling noises",
						description: "rales / rhonchi",
					},
					{
						id: "bronchial_breathing",
						label: "Bronchial breathing",
						description: "increased peripheral breath sounds",
					},
					{
						id: "noisy_breathing",
						label: "Noisy / funny-sounding breathing",
					},
				],
			},
			{
				name: "Cough",
				symptoms: [
					{
						id: "dry_cough",
						label: "Dry cough",
						description: "persistent / chronic",
					},
					{ id: "morning_cough", label: "Cough worse in the morning" },
					{
						id: "productive_cough",
						label: "Cough with discolored mucus",
						description: "yellow, green, thick, or bloody sputum",
					},
					{ id: "frothy_mucus", label: "Coughing up frothy mucus" },
					{
						id: "hemoptysis",
						label: "Coughing up blood",
						description: "hemoptysis",
					},
				],
			},
			{
				name: "Nasal & Throat",
				symptoms: [
					{ id: "sore_throat", label: "Sore throat" },
					{ id: "nasal_congestion", label: "Nasal congestion" },
					{ id: "runny_nose", label: "Runny nose" },
					{ id: "hoarseness", label: "Hoarseness" },
					{
						id: "dysphagia",
						label: "Difficulty swallowing",
						description: "dysphagia",
					},
					{
						id: "anosmia_dysgeusia",
						label: "Loss of / altered smell or taste",
						description: "anosmia / dysgeusia",
					},
				],
			},
			{
				name: "Infections & Lung Complications",
				symptoms: [
					{
						id: "recurrent_infections",
						label: "Recurring respiratory infections",
						description: "e.g., bronchitis or pneumonia",
					},
				],
			},
		],
	},
	{
		topic: "Chest, Heart & Circulation Symptoms",
		groups: [
			{
				name: "Chest Sensations",
				symptoms: [
					{
						id: "chest_pain",
						label: "Chest pain, pressure, tightness, or heaviness",
						description: "especially when breathing deeply or coughing",
					},
					{ id: "unilateral_chest_pain", label: "Pain on one side of the chest" },
					{
						id: "back_pain",
						label: "Back pain associated with breathing",
					},
				],
			},
			{
				name: "Heart & Circulation",
				symptoms: [
					{
						id: "tachycardia",
						label: "Rapid heart rate",
						description: "tachycardia",
					},
					{
						id: "palpitations",
						label: "Heart palpitations / fluttering",
					},
					{
						id: "loud_heartbeat",
						label: "Loud heartbeat sound",
						description: "associated with pulmonary hypertension",
					},
					{
						id: "cyanosis",
						label: "Bluish, gray, or white skin, lips, or nails",
						description: "cyanosis",
					},
					{
						id: "edema",
						label: "Swelling in legs, feet, belly, or skin",
						description: "edema",
					},
				],
			},
		],
	},
	{
		topic: "Neurological, Mental & Sleep Symptoms",
		groups: [
			{
				symptoms: [
					{ id: "anxiety", label: "Anxiety" },
					{
						id: "confusion",
						label: "Confusion / altered mental state",
					},
					{ id: "depression", label: "Depression" },
					{
						id: "insomnia",
						label: "Difficulty sleeping",
						description: "insomnia",
					},
					{ id: "dizziness", label: "Dizziness" },
					{ id: "syncope", label: "Fainting", description: "syncope" },
					{ id: "headaches", label: "Headaches" },
					{
						id: "unable_to_wake",
						label: "Inability to wake up or stay awake",
					},
					{
						id: "brain_fog",
						label: 'Trouble thinking or focusing ("brain fog")',
					},
				],
			},
		],
	},
	{
		topic: "Whole-Body (Systemic) Symptoms",
		groups: [
			{
				symptoms: [
					{
						id: "fatigue",
						label: "Fatigue",
						description: "tiredness, extreme fatigue, lack of energy",
					},
					{
						id: "fever",
						label: "Fever",
						description: "including high fever up to 105°F / 40°C",
					},
					{
						id: "hypothermia",
						label: "Low body temperature",
						description: "hypothermia",
					},
					{ id: "chills_sweating", label: "Chills / sweating" },
					{
						id: "muscle_aches",
						label: "Muscle pain / body aches",
					},
					{ id: "weight_loss", label: "Unexplained weight loss" },
					{ id: "clubbed_fingers", label: "Clubbed fingers" },
					{ id: "barrel_chest", label: "Barrel-shaped chest" },
				],
			},
			{
				name: "Infant-Specific Signs",
				symptoms: [
					{ id: "irritability", label: "Irritability" },
					{ id: "lethargy", label: "Listlessness / lethargy" },
					{
						id: "hypotonia",
						label: "Low muscle tone",
						description: 'feeling "floppy"',
					},
					{
						id: "poor_feeding",
						label: "Refusal to feed or drink",
					},
				],
			},
		],
	},
	{
		topic: "Gastrointestinal & Abdominal Symptoms",
		groups: [
			{
				symptoms: [
					{ id: "abdominal_pain", label: "Abdominal pain / belly aches" },
					{ id: "gas_bloating", label: "Gas / bloating" },
					{ id: "appetite_loss", label: "Loss of appetite" },
					{ id: "nausea_vomiting", label: "Nausea and vomiting" },
					{ id: "diarrhea", label: "Diarrhea" },
					{
						id: "hernia_bulge",
						label: "Visible lump or bulge",
						description:
							"classic hernia signs — appears with activity or positioning, reducible",
					},
				],
			},
		],
	},
];

export const ALL_SYMPTOM_TAGS: SymptomTag[] = SYMPTOM_TOPICS.flatMap(
	(t) => t.groups.flatMap((g) => g.symptoms),
);

export function symptomLabelById(id: string): string | undefined {
	return ALL_SYMPTOM_TAGS.find((s) => s.id === id)?.label;
}
