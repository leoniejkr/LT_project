package api

import "backend/internal/chat"

// ChatRequest is the request contract of the public chat endpoint.
type ChatRequest struct {
	Message string         `json:"message"`
	History []chat.Message `json:"history"`
	Context map[string]any `json:"context,omitempty"`
	Model   string         `json:"model,omitempty"`
}
