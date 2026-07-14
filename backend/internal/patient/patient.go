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
func (i *Illnesses) Scan(value interface{}) error {
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

const (
	SymptomCough             Symptom = "Cough"
	SymptomFever             Symptom = "Fever"
	SymptomShortnessOfBreath Symptom = "Shortness of Breath"
	SymptomFatigue           Symptom = "Fatigue"
)

type Symptoms []Symptom

func (s *Symptoms) Scan(value interface{}) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, &s)
}

func (s Symptoms) Value() (driver.Value, error) {
	return json.Marshal(s)
}

type DicomPaths []string

func (p *DicomPaths) Scan(value interface{}) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, &p)
}

func (p DicomPaths) Value() (driver.Value, error) {
	return json.Marshal(p)
}

type Patient struct {
	ID             uint       `gorm:"primaryKey" json:"id"`
	Age            uint       `gorm:"not null" json:"age"`
	Gender         Gender     `gorm:"not null" json:"gender"`
	KnownIllnesses Illnesses  `gorm:"type:jsonb" json:"knownIllnesses"`
	Symptoms       Symptoms   `gorm:"type:jsonb" json:"symptoms"`
	XRayPaths      DicomPaths `gorm:"type:jsonb" json:"dicomPaths"`
}
