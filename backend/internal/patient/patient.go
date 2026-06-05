package patient

// das domänenmodell / structs

type Gender string

const (
	GenderFemale  Gender = "Female"
	GenderMale    Gender = "Male"
	GenderDiverse Gender = "Diverse"
)

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
	id                 string // potentiell unnötig, aber sicherheitshalber drin
	age                int
	gender             Gender
	admittedToIcu      bool
	requiresVentilator bool
	knownIllnesses     []Illness
	symptoms           []Symptom
}
