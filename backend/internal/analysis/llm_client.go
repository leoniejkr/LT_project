package analysis

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
)

type PredictionResponse struct {
	Status            string  `json:"status"`
	Prediction        string  `json:"prediction"`
	Confidence        float64 `json:"confidence"`
	Confidence_Reason string  `json:"confidence_reason"`
	ModelVersion      string  `json:"model_version"`
	IsMock            bool    `json:"is_mock"`
}

type LLMClient struct {
	baseURL string
}

func NewLLMClient() *LLMClient {
	url := os.Getenv("MODELLING_URL")
	if url == "" {
		url = "http://modelling:5000"
	}
	return &LLMClient{baseURL: url}
}

func (c *LLMClient) GetPrediction() (*PredictionResponse, error) {
	resp, err := http.Post(c.baseURL+"/predict", "application/json", bytes.NewBuffer([]byte("{}")))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("modelling service returned status: %d", resp.StatusCode)
	}

	var prediction PredictionResponse
	if err := json.NewDecoder(resp.Body).Decode(&prediction); err != nil {
		return nil, err
	}

	return &prediction, nil
}
