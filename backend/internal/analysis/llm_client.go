package analysis

import (
	"bytes"
	"encoding/json"
	"fmt"
	"mime/multipart"
	"os"

	httpclient "backend/internal/http"
)

type LLMClient struct {
	client *httpclient.Client
}

func NewLLMClient() *LLMClient {
	baseURL := os.Getenv("MODELLING_URL")
	if baseURL == "" {
		baseURL = "http://localhost:5000"
	}
	return &LLMClient{client: httpclient.New(baseURL)}
}

func (c *LLMClient) GetPrediction(patientData any, imageBuffers [][]byte, imageNames []string, classifierModel, llmModel string) (*ModelPredictionResponse, error) {
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

	var result ModelPredictionResponse
	if err := c.client.Post("/predict", writer.FormDataContentType(), &body, &result); err != nil {
		return nil, fmt.Errorf("failed to call modelling service: %w", err)
	}
	return &result, nil
}
