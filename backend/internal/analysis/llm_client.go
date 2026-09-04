package analysis

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
)

type PredictionResponse struct {
	Status       string      `json:"status"`
	ModelVersion string      `json:"model_version"`
	Predictions  Predictions `json:"predictions"`
	ImageResults ImageResults `json:"image_results"`
	IsMock       bool        `json:"is_mock"`
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

func (c *LLMClient) GetPrediction(patientData any, imageBuffers [][]byte, imageNames []string, classifierModel, llmModel string) (*PredictionResponse, error) {
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)

	jsonBytes, err := json.Marshal(patientData)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal patient data: %w", err)
	}

	if err := writer.WriteField("formData", string(jsonBytes)); err != nil {
		return nil, fmt.Errorf("failed to write formData field: %w", err)
	}

	// Forward the user's model selections to the modelling service.
	if classifierModel != "" {
		if err := writer.WriteField("classifier_model", classifierModel); err != nil {
			return nil, fmt.Errorf("failed to write classifier_model field: %w", err)
		}
	}
	if llmModel != "" {
		if err := writer.WriteField("llm_model", llmModel); err != nil {
			return nil, fmt.Errorf("failed to write llm_model field: %w", err)
		}
	}

	for i, buf := range imageBuffers {
		part, err := writer.CreateFormFile("image_files", imageNames[i])
		if err != nil {
			return nil, fmt.Errorf("failed to create form file: %w", err)
		}
		if _, err := part.Write(buf); err != nil {
			return nil, fmt.Errorf("failed to write image data: %w", err)
		}
	}

	if err := writer.Close(); err != nil {
		return nil, fmt.Errorf("failed to close multipart writer: %w", err)
	}

	req, err := http.NewRequest("POST", c.baseURL+"/predict", &body)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", writer.FormDataContentType())

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to call modelling service: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("modelling service returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result PredictionResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode modelling response: %w", err)
	}

	return &result, nil
}
