package analysis

import (
	"database/sql/driver"
	"encoding/json"
	"errors"
)

type Prediction struct {
	Class      string  `json:"class"`
	Confidence float64 `json:"confidence"`
	Reason     string  `json:"reason,omitempty"`
}

type Predictions []Prediction

func (p *Predictions) Scan(value any) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, p)
}

func (p Predictions) Value() (driver.Value, error) {
	return json.Marshal(p)
}

type ImagePrediction struct {
	Class      string  `json:"class"`
	Confidence float64 `json:"confidence"`
	Heatmap    string  `json:"heatmap,omitempty"`
	OrthancID  string  `json:"orthancId,omitempty"`
}

type ImagePredictions []ImagePrediction

func (ip *ImagePredictions) Scan(value any) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, ip)
}

func (ip ImagePredictions) Value() (driver.Value, error) {
	return json.Marshal(ip)
}

type ImageResult struct {
	Index       int              `json:"index"`
	Filename    string           `json:"filename"`
	Predictions ImagePredictions `json:"predictions"`
}

type ImageResults []ImageResult

func (ir *ImageResults) Scan(value any) error {
	bytes, ok := value.([]byte)
	if !ok {
		return errors.New("type assertion to []byte failed")
	}
	return json.Unmarshal(bytes, ir)
}

func (ir ImageResults) Value() (driver.Value, error) {
	return json.Marshal(ir)
}

type Analysis struct {
	ID               uint         `gorm:"primaryKey" json:"id"`
	PatientID        uint         `gorm:"not null;index" json:"patientId"`
	Prediction       string       `json:"prediction,omitempty"`
	Confidence       float64      `json:"confidence,omitempty"`
	ConfidenceReason string       `json:"confidenceReason,omitempty"`
	Status           string       `json:"status"`
	ModelVersion     string       `json:"modelVersion,omitempty"`
	Predictions      Predictions  `gorm:"type:jsonb" json:"predictions"`
	ImageResults     ImageResults `gorm:"type:jsonb" json:"imageResults"`
}

// ModelPredictionResponse is the response contract of the modelling service.
// API handlers map it to their own response DTOs before sending it to clients.
type ModelPredictionResponse struct {
	Status       string       `json:"status"`
	ModelVersion string       `json:"model_version"`
	Predictions  Predictions  `json:"predictions"`
	ImageResults ImageResults `json:"image_results"`
}
