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
	SymptomApnea               Symptom = "Pauses in breathing"
	SymptomGrunting            Symptom = "Grunting"
	SymptomShallowBreathing    Symptom = "Shallow breathing"
	SymptomShortnessOfBreath   Symptom = "Shortness of breath"
	SymptomCatchingBreath      Symptom = "Difficulty catching breath"
	SymptomDeepBreath          Symptom = "Inability to take a deep breath"
	SymptomAirHunger           Symptom = "Constant feeling of not getting enough air"
	SymptomSuffocation         Symptom = "Feeling like suffocating / gasping for air"
	SymptomNocturnalDyspnea    Symptom = "Breathlessness that awakens you from sleep"
	SymptomOrthopnea           Symptom = "Orthopnea"
	SymptomTachypnea           Symptom = "Rapid breathing"
	SymptomRetractions         Symptom = "Increased work of breathing"
	SymptomWheezing            Symptom = "Wheezing"
	SymptomStridor             Symptom = "Stridor"
	SymptomCrepitus            Symptom = "Crepitus"
	SymptomRalesRhonchi        Symptom = "Rattling noises"
	SymptomBronchialBreathing  Symptom = "Bronchial breathing"
	SymptomNoisyBreathing      Symptom = "Noisy / funny-sounding breathing"
	SymptomDryCough            Symptom = "Dry cough"
	SymptomMorningCough        Symptom = "Cough worse in the morning"
	SymptomProductiveCough     Symptom = "Cough with discolored mucus"
	SymptomFrothyMucus         Symptom = "Coughing up frothy mucus"
	SymptomHemoptysis          Symptom = "Coughing up blood"
	SymptomSoreThroat          Symptom = "Sore throat"
	SymptomNasalCongestion     Symptom = "Nasal congestion"
	SymptomRunnyNose           Symptom = "Runny nose"
	SymptomHoarseness          Symptom = "Hoarseness"
	SymptomDysphagia           Symptom = "Difficulty swallowing"
	SymptomAnosmiaDysgeusia    Symptom = "Loss of / altered smell or taste"
	SymptomRecurrentInfections Symptom = "Recurring respiratory infections"

	// Chest, Heart & Circulation Symptoms
	SymptomChestPain      Symptom = "Chest pain, pressure, tightness, or heaviness"
	SymptomUnilateralPain Symptom = "Pain on one side of the chest"
	SymptomBackPain       Symptom = "Back pain associated with breathing"
	SymptomTachycardia    Symptom = "Rapid heart rate"
	SymptomPalpitations   Symptom = "Heart palpitations / fluttering"
	SymptomLoudHeartbeat  Symptom = "Loud heartbeat sound"
	SymptomCyanosis       Symptom = "Bluish, gray, or white skin, lips, or nails"
	SymptomEdema          Symptom = "Swelling in legs, feet, belly, or skin"

	// Neurological, Mental & Sleep Symptoms
	SymptomAnxiety      Symptom = "Anxiety"
	SymptomConfusion    Symptom = "Confusion / altered mental state"
	SymptomDepression   Symptom = "Depression"
	SymptomInsomnia     Symptom = "Difficulty sleeping"
	SymptomDizziness    Symptom = "Dizziness"
	SymptomSyncope      Symptom = "Fainting"
	SymptomHeadaches    Symptom = "Headaches"
	SymptomUnableToWake Symptom = "Inability to wake up or stay awake"
	SymptomBrainFog     Symptom = "Trouble thinking or focusing"

	// Whole-Body (Systemic) Symptoms
	SymptomFatigue        Symptom = "Fatigue"
	SymptomFever          Symptom = "Fever"
	SymptomHypothermia    Symptom = "Low body temperature"
	SymptomChills         Symptom = "Chills / sweating"
	SymptomMuscleAches    Symptom = "Muscle pain / body aches"
	SymptomWeightLoss     Symptom = "Unexplained weight loss"
	SymptomClubbedFingers Symptom = "Clubbed fingers"
	SymptomBarrelChest    Symptom = "Barrel-shaped chest"

	// Infant-Specific Signs
	SymptomIrritability Symptom = "Irritability"
	SymptomLethargy     Symptom = "Listlessness / lethargy"
	SymptomHypotonia    Symptom = "Low muscle tone"
	SymptomPoorFeeding  Symptom = "Refusal to feed or drink"

	// Gastrointestinal & Abdominal Symptoms
	SymptomAbdominalPain  Symptom = "Abdominal pain / belly aches"
	SymptomGasBloating    Symptom = "Gas / bloating"
	SymptomAppetiteLoss   Symptom = "Loss of appetite"
	SymptomNauseaVomiting Symptom = "Nausea and vomiting"
	SymptomDiarrhea       Symptom = "Diarrhea"
	SymptomHerniaBulge    Symptom = "Visible lump or bulge"
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
