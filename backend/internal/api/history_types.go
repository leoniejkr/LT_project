package api

import (
	"backend/internal/analysis"
	"backend/internal/patient"
)

type PatientSummary struct {
	ID     uint           `json:"id"`
	Age    uint           `json:"age"`
	Gender patient.Gender `json:"gender"`
}

type PatientAnalysisResponse struct {
	Status   string                       `json:"status"`
	Patient  *patient.Patient             `json:"patient"`
	Analysis *analysis.PredictionResponse `json:"analysis"`
}
