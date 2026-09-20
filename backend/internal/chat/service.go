package chat

import (
	"fmt"
	"net/http"
	"os"
	"time"

	httpclient "backend/internal/http"
)

type Service struct {
	client *httpclient.Client
	model  string
}

func NewService(baseURL, model string, httpClient *http.Client) *Service {
	if baseURL == "" {
		baseURL = os.Getenv("OLLAMA_URL")
		if baseURL == "" {
			baseURL = "http://localhost:11434"
		}
	}
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 300 * time.Second}
	}
	return &Service{
		client: httpclient.New(baseURL, httpclient.WithHTTPClient(httpClient)),
		model:  model,
	}
}

func (s *Service) SendMessage(messages []Message, model string) (string, error) {
	if model == "" {
		model = s.model
	}

	var result ChatResponse
	if err := s.client.PostJSON("/api/chat", ChatRequest{
		Model:    model,
		Messages: messages,
		Stream:   false,
		Options: Options{
			Temperature: 0.3,
			NumPredict:  1024,
			NumCtx:      8192,
		},
	}, &result); err != nil {
		return "", fmt.Errorf("failed to call ollama: %w", err)
	}

	return result.Message.Content, nil
}