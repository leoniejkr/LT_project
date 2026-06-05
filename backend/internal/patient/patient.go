package patient

// das domänenmodell / structs

type Illness string

const (
	IllnessCovid     Illness = "Covid19"
	IllnessPneumonia Illness = "Pneumonia"
	IllnessEmphysema Illness = "Emphysema"
	IllnessEffusion  Illness = "Effusion"
	IllnessFibrosis  Illness = "Fibrosis"
)

type Symptom string

const (
	SymptomCough             Symptom = "Cough"
	SymptomFever             Symptom = "Fever"
	SymptomShortnessOfBreath Symptom = "Shortness of Breath"
	SymptomFatigue           Symptom = "Fatigue"
)

type Patient struct {
	id                 string
	age                int // potentiell unnötig, aber sicherheitshalber drin
	gender             string
	admittedToIcu      bool
	requiresVentilator bool
	knownIllnesses     []Illness
	symptoms           []Symptom
}
