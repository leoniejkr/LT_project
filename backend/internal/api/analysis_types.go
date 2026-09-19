package api

import (
	"backend/internal/analysis"
	"backend/internal/patient"
)

// AnalysisResponse is the public API contract for an analysis result. It is
// deliberately separate from analysis.ModelPredictionResponse, which is the
// contract of the internal modelling service.
type AnalysisResponse struct {
	Status       string        `json:"status"`
	ModelVersion string        `json:"model_version"`
	Predictions  []Prediction  `json:"predictions"`
	ImageResults []ImageResult `json:"image_results"`
}

type Prediction struct {
	Class      string  `json:"class"`
	Confidence float64 `json:"confidence"`
	Reason     string  `json:"reason,omitempty"`
}

type ImagePrediction struct {
	Class      string  `json:"class"`
	Confidence float64 `json:"confidence"`
	Heatmap    string  `json:"heatmap,omitempty"`
	OrthancID  string  `json:"orthancId,omitempty"`
}

type ImageResult struct {
	Index       int               `json:"index"`
	Filename    string            `json:"filename"`
	Predictions []ImagePrediction `json:"predictions"`
}

// AnalysisResultResponse is returned after a newly created analysis.
type AnalysisResultResponse struct {
	Status   string           `json:"status"`
	Patient  *PatientResponse `json:"patient"`
	Analysis AnalysisResponse `json:"analysis"`
}

// PatientResponse is the public representation of a patient in analysis responses.
type PatientResponse struct {
	ID         uint     `json:"id"`
	Age        uint     `json:"age"`
	Gender     string   `json:"gender"`
	Symptoms   []string `json:"symptoms"`
	History    []string `json:"history"`
	OrthancIDs []string `json:"orthancIDs"`
}

func newAnalysisResponse(status, modelVersion string, predictions analysis.Predictions, imageResults analysis.ImageResults) AnalysisResponse {
	result := AnalysisResponse{
		Status: status, ModelVersion: modelVersion,
		Predictions:  make([]Prediction, len(predictions)),
		ImageResults: make([]ImageResult, len(imageResults)),
	}
	for i, prediction := range predictions {
		result.Predictions[i] = Prediction{Class: prediction.Class, Confidence: prediction.Confidence, Reason: prediction.Reason}
	}
	for i, image := range imageResults {
		predictions := make([]ImagePrediction, len(image.Predictions))
		for j, prediction := range image.Predictions {
			predictions[j] = ImagePrediction{Class: prediction.Class, Confidence: prediction.Confidence, Heatmap: prediction.Heatmap, OrthancID: prediction.OrthancID}
		}
		result.ImageResults[i] = ImageResult{Index: image.Index, Filename: image.Filename, Predictions: predictions}
	}
	return result
}

func newAnalysisResponseFromModel(response *analysis.ModelPredictionResponse) AnalysisResponse {
	return newAnalysisResponse(response.Status, response.ModelVersion, response.Predictions, response.ImageResults)
}

func newAnalysisResponseFromStored(stored *analysis.Analysis) AnalysisResponse {
	return newAnalysisResponse(stored.Status, stored.ModelVersion, stored.Predictions, stored.ImageResults)
}

func newPatientResponse(source *patient.Patient) *PatientResponse {
	symptoms := make([]string, len(source.Symptoms))
	for i, symptom := range source.Symptoms {
		symptoms[i] = string(symptom)
	}
	history := make([]string, len(source.History))
	for i, entry := range source.History {
		history[i] = string(entry)
	}
	return &PatientResponse{
		ID: source.ID, Age: source.Age, Gender: string(source.Gender),
		Symptoms: symptoms, History: history, OrthancIDs: append([]string(nil), source.OrthancIDs...),
	}
}
