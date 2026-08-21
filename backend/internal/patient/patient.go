package patient

import (
	"database/sql/driver"
	"encoding/json"
	"errors"
)

type Gender string

const (
	GenderFemale  Gender = "Female"
	GenderMale    Gender = "Male"
	GenderDiverse Gender = "Diverse"
)

type Illness string

// Illnesses ist ein Hilfstyp für das Speichern von Slices als JSONB in Postgres
type Illnesses []Illness

const (
	IllnessCovid     Illness = "Covid19"
	IllnessPneumonia Illness = "Pneumonia"
	IllnessEmphysema Illness = "Emphysema"
	IllnessEffusion  Illness = "Effusion"
	IllnessFibrosis  Illness = "Fibrosis"
)

// wird benötigt für speicherung von go slices in postgres
func (i *Illnesses) Scan(value any) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, &i)
}

// wird benötigt für speicherung von go slices in postgres
func (i Illnesses) Value() (driver.Value, error) {
	return json.Marshal(i)
}

type Symptom string

// Symptom vocabulary grouped by topic. Values must match the labels
// defined in frontend/src/lib/symptoms.ts.
const (
	// Breathing & Respiratory Symptoms
	SymptomApnea               Symptom = "Pauses in breathing (apnea)"
	SymptomGrunting            Symptom = "Grunting"
	SymptomShallowBreathing    Symptom = "Shallow breathing"
	SymptomShortnessOfBreath   Symptom = "Shortness of breath (dyspnea)"
	SymptomCatchingBreath      Symptom = "Difficulty catching breath"
	SymptomDeepBreath          Symptom = "Inability to take a deep breath"
	SymptomAirHunger           Symptom = "Constant feeling of not getting enough air"
	SymptomSuffocation         Symptom = "Feeling like suffocating / gasping for air"
	SymptomNocturnalDyspnea    Symptom = "Breathlessness that awakens you from sleep"
	SymptomOrthopnea           Symptom = "Orthopnea (difficulty breathing unless sitting upright)"
	SymptomTachypnea           Symptom = "Rapid breathing (tachypnea)"
	SymptomRetractions         Symptom = "Increased work of breathing (retractions)"
	SymptomWheezing            Symptom = "Wheezing"
	SymptomStridor             Symptom = "Stridor"
	SymptomCrepitus            Symptom = "Crepitus (crackling under the skin)"
	SymptomRalesRhonchi        Symptom = "Rattling noises (rales/rhonchi)"
	SymptomBronchialBreathing  Symptom = "Bronchial breathing (increased peripheral breath sounds)"
	SymptomNoisyBreathing      Symptom = "Noisy / funny-sounding breathing"
	SymptomDryCough            Symptom = "Dry cough (persistent / chronic)"
	SymptomMorningCough        Symptom = "Cough worse in the morning"
	SymptomProductiveCough     Symptom = "Cough with yellow, green, thick, or bloody mucus"
	SymptomFrothyMucus         Symptom = "Coughing up frothy mucus"
	SymptomHemoptysis          Symptom = "Coughing up blood (hemoptysis)"
	SymptomSoreThroat          Symptom = "Sore throat"
	SymptomNasalCongestion     Symptom = "Nasal congestion"
	SymptomRunnyNose           Symptom = "Runny nose"
	SymptomHoarseness          Symptom = "Hoarseness"
	SymptomDysphagia           Symptom = "Difficulty swallowing (dysphagia)"
	SymptomAnosmiaDysgeusia    Symptom = "Loss of / altered smell or taste (anosmia/dysgeusia)"
	SymptomRecurrentInfections Symptom = "Recurring respiratory infections (bronchitis, pneumonia)"

	// Chest, Heart & Circulation Symptoms
	SymptomChestPain      Symptom = "Chest pain, pressure, tightness, or heaviness"
	SymptomUnilateralPain Symptom = "Pain on one side of the chest"
	SymptomBackPain       Symptom = "Back pain associated with breathing"
	SymptomTachycardia    Symptom = "Rapid heart rate (tachycardia)"
	SymptomPalpitations   Symptom = "Heart palpitations / fluttering"
	SymptomLoudHeartbeat  Symptom = "Loud heartbeat sound (pulmonary hypertension)"
	SymptomCyanosis       Symptom = "Bluish, gray, or white skin, lips, or nails (cyanosis)"
	SymptomEdema          Symptom = "Swelling in legs, feet, belly, or skin (edema)"

	// Neurological, Mental & Sleep Symptoms
	SymptomAnxiety      Symptom = "Anxiety"
	SymptomConfusion    Symptom = "Confusion / altered mental state"
	SymptomDepression   Symptom = "Depression"
	SymptomInsomnia     Symptom = "Difficulty sleeping (insomnia)"
	SymptomDizziness    Symptom = "Dizziness"
	SymptomSyncope      Symptom = "Fainting (syncope)"
	SymptomHeadaches    Symptom = "Headaches"
	SymptomUnableToWake Symptom = "Inability to wake up or stay awake"
	SymptomBrainFog     Symptom = `Trouble thinking or focusing ("brain fog")`

	// Whole-Body (Systemic) Symptoms
	SymptomFatigue        Symptom = "Fatigue"
	SymptomFever          Symptom = "Fever (up to 105°F / 40°C)"
	SymptomHypothermia    Symptom = "Low body temperature (hypothermia)"
	SymptomChills         Symptom = "Chills / sweating"
	SymptomMuscleAches    Symptom = "Muscle pain / body aches"
	SymptomWeightLoss     Symptom = "Unexplained weight loss"
	SymptomClubbedFingers Symptom = "Clubbed fingers"
	SymptomBarrelChest    Symptom = "Barrel-shaped chest"

	// Infant-Specific Signs
	SymptomIrritability Symptom = "Irritability"
	SymptomLethargy     Symptom = "Listlessness / lethargy"
	SymptomHypotonia    Symptom = `Low muscle tone ("floppy")`
	SymptomPoorFeeding  Symptom = "Refusal to feed or drink"

	// Gastrointestinal & Abdominal Symptoms
	SymptomAbdominalPain  Symptom = "Abdominal pain / belly aches"
	SymptomGasBloating    Symptom = "Gas / bloating"
	SymptomAppetiteLoss   Symptom = "Loss of appetite"
	SymptomNauseaVomiting Symptom = "Nausea and vomiting"
	SymptomDiarrhea       Symptom = "Diarrhea"
	SymptomHerniaBulge    Symptom = "Visible lump or bulge (hernia signs)"
)

type Symptoms []Symptom

func (s *Symptoms) Scan(value any) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, &s)
}

func (s Symptoms) Value() (driver.Value, error) {
	return json.Marshal(s)
}

type ImagePaths []string

func (p *ImagePaths) Scan(value any) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, &p)
}

func (p ImagePaths) Value() (driver.Value, error) {
	return json.Marshal(p)
}

type Patient struct {
	ID             uint       `gorm:"primaryKey" json:"id"`
	Age            uint       `gorm:"not null" json:"age"`
	Gender         Gender     `gorm:"not null" json:"gender"`
	KnownIllnesses Illnesses  `gorm:"type:jsonb" json:"knownIllnesses"`
	Symptoms       Symptoms   `gorm:"type:jsonb" json:"symptoms"`
	OrthancIDs     ImagePaths `gorm:"type:jsonb" json:"orthancIDs"`
}
