package api

import "backend/internal/chat"

type ChatRequest struct {
	Message string         `json:"message"`
	History []chat.Message `json:"history"`
	Context *ChatContext   `json:"context,omitempty"`
	Model   string         `json:"model,omitempty"`
}

type ChatContext struct {
	Patient  *ChatPatientContext  `json:"patient,omitempty"`
	Analysis *ChatAnalysisContext `json:"analysis,omitempty"`
}

type ChatPatientContext struct {
	Age      *uint    `json:"age,omitempty"`
	Gender   *string  `json:"gender,omitempty"`
	Symptoms []string `json:"symptoms,omitempty"`
	History  []string `json:"history,omitempty"`
}

type ChatAnalysisContext struct {
	ModelVersion *string                 `json:"model_version,omitempty"`
	Predictions  []ChatPredictionContext `json:"predictions,omitempty"`
}

type ChatPredictionContext struct {
	Class      string  `json:"class"`
	Confidence float64 `json:"confidence"`
}
