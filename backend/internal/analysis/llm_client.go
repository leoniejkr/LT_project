package analysis

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
)

type PredictionResponse struct {
	Status           string  `json:"status"`
	Prediction       string  `json:"prediction"`
	Confidence       float64 `json:"confidence"`
	ConfidenceReason string  `json:"confidence_reason"`
	ModelVersion     string  `json:"model_version"`
}

type LLMClient struct {
	baseURL    string
	httpClient *http.Client
}

func NewLLMClient() *LLMClient {
	baseURL := os.Getenv("MODELLING_URL")
	if baseURL == "" {
		baseURL = "http://localhost:5000"
	}
	return &LLMClient{
		baseURL:    baseURL,
		httpClient: &http.Client{},
	}
}

func (c *LLMClient) GetPrediction(patientData any) (*PredictionResponse, error) {
	body, err := json.Marshal(patientData)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal patient data: %w", err)
	}

	resp, err := c.httpClient.Post(c.baseURL+"/predict", "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("failed to call modelling service: %w", err)
	}
	defer resp.Body.Close()

	var result PredictionResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode modelling response: %w", err)
	}

	return &result, nil
}
