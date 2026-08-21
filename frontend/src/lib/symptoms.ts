export interface SymptomTag {
	id: string;
	label: string;
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
					{ id: "apnea", label: "Pauses in breathing (apnea)" },
					{ id: "grunting", label: "Grunting" },
					{ id: "shallow_breathing", label: "Shallow breathing" },
				],
			},
			{
				name: "Breathing Difficulty / Dyspnea",
				symptoms: [
					{ id: "dyspnea", label: "Shortness of breath (dyspnea)" },
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
						label: "Orthopnea (difficulty breathing unless sitting upright)",
					},
				],
			},
			{
				name: "Breathing Rate & Effort",
				symptoms: [
					{ id: "tachypnea", label: "Rapid breathing (tachypnea)" },
					{
						id: "retractions",
						label: "Increased work of breathing (retractions)",
					},
				],
			},
			{
				name: "Breathing Sounds",
				symptoms: [
					{ id: "wheezing", label: "Wheezing" },
					{ id: "stridor", label: "Stridor" },
					{ id: "crepitus", label: "Crepitus (crackling under the skin)" },
					{ id: "rales_rhonchi", label: "Rattling noises (rales/rhonchi)" },
					{
						id: "bronchial_breathing",
						label: "Bronchial breathing (increased peripheral breath sounds)",
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
					{ id: "dry_cough", label: "Dry cough (persistent / chronic)" },
					{ id: "morning_cough", label: "Cough worse in the morning" },
					{
						id: "productive_cough",
						label: "Cough with yellow, green, thick, or bloody mucus",
					},
					{ id: "frothy_mucus", label: "Coughing up frothy mucus" },
					{ id: "hemoptysis", label: "Coughing up blood (hemoptysis)" },
				],
			},
			{
				name: "Nasal & Throat",
				symptoms: [
					{ id: "sore_throat", label: "Sore throat" },
					{ id: "nasal_congestion", label: "Nasal congestion" },
					{ id: "runny_nose", label: "Runny nose" },
					{ id: "hoarseness", label: "Hoarseness" },
					{ id: "dysphagia", label: "Difficulty swallowing (dysphagia)" },
					{
						id: "anosmia_dysgeusia",
						label: "Loss of / altered smell or taste (anosmia/dysgeusia)",
					},
				],
			},
			{
				name: "Infections & Lung Complications",
				symptoms: [
					{
						id: "recurrent_infections",
						label: "Recurring respiratory infections (bronchitis, pneumonia)",
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
					},
					{
						id: "unilateral_chest_pain",
						label: "Pain on one side of the chest",
					},
					{
						id: "back_pain",
						label: "Back pain associated with breathing",
					},
				],
			},
			{
				name: "Heart & Circulation",
				symptoms: [
					{ id: "tachycardia", label: "Rapid heart rate (tachycardia)" },
					{
						id: "palpitations",
						label: "Heart palpitations / fluttering",
					},
					{
						id: "loud_heartbeat",
						label: "Loud heartbeat sound (pulmonary hypertension)",
					},
					{
						id: "cyanosis",
						label: "Bluish, gray, or white skin, lips, or nails (cyanosis)",
					},
					{
						id: "edema",
						label: "Swelling in legs, feet, belly, or skin (edema)",
					},
				],
			},
		],
	},
	{
		topic: "Neurological, Mental & Sleep Symptoms",
		groups: [
			{
				name: "General",
				symptoms: [
					{ id: "anxiety", label: "Anxiety" },
					{
						id: "confusion",
						label: "Confusion / altered mental state",
					},
					{ id: "depression", label: "Depression" },
					{ id: "insomnia", label: "Difficulty sleeping (insomnia)" },
					{ id: "dizziness", label: "Dizziness" },
					{ id: "syncope", label: "Fainting (syncope)" },
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
				name: "General Signs",
				symptoms: [
					{ id: "fatigue", label: "Fatigue" },
					{ id: "fever", label: "Fever (up to 105°F / 40°C)" },
					{
						id: "hypothermia",
						label: "Low body temperature (hypothermia)",
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
						label: 'Low muscle tone ("floppy")',
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
				name: "General",
				symptoms: [
					{ id: "abdominal_pain", label: "Abdominal pain / belly aches" },
					{ id: "gas_bloating", label: "Gas / bloating" },
					{ id: "appetite_loss", label: "Loss of appetite" },
					{ id: "nausea_vomiting", label: "Nausea and vomiting" },
					{ id: "diarrhea", label: "Diarrhea" },
					{
						id: "hernia_bulge",
						label: "Visible lump or bulge (hernia signs)",
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
