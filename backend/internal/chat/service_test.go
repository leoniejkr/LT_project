package chat

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestSendMessage_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/api/chat" {
			t.Errorf("expected /api/chat, got %s", r.URL.Path)
		}

		var req ChatRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("failed to decode request: %v", err)
		}
		if req.Model != "test-model" {
			t.Errorf("model = %q, want %q", req.Model, "test-model")
		}
		if req.Stream {
			t.Error("stream should be false")
		}
		if len(req.Messages) != 2 || req.Messages[0].Role != "user" {
			t.Errorf("unexpected messages: %+v", req.Messages)
		}
		if req.Options.NumPredict != 1024 {
			t.Errorf("num_predict = %d, want 1024 (long replies must not be cut)", req.Options.NumPredict)
		}
		if req.Options.NumCtx != 8192 {
			t.Errorf("num_ctx = %d, want 8192", req.Options.NumCtx)
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(ChatResponse{
			Message: Message{Role: "assistant", Content: "Hello there"},
		})
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", &http.Client{Timeout: 5 * time.Second})

	reply, err := service.SendMessage([]Message{
		{Role: "user", Content: "Hello"},
		{Role: "user", Content: "How are you?"},
	}, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if reply != "Hello there" {
		t.Errorf("reply = %q, want %q", reply, "Hello there")
	}
}

func TestSendMessage_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("model overloaded"))
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", &http.Client{})

	_, err := service.SendMessage([]Message{{Role: "user", Content: "hi"}}, "")
	if err == nil {
		t.Fatal("expected error for server error response")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Errorf("error should contain status code 500, got: %v", err)
	}
}

func TestSendMessage_InvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte("not json"))
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", &http.Client{})

	_, err := service.SendMessage([]Message{{Role: "user", Content: "hi"}}, "")
	if err == nil {
		t.Fatal("expected error for invalid JSON response")
	}
	if !strings.Contains(err.Error(), "decode") {
		t.Errorf("error should mention decode failure, got: %v", err)
	}
}

func TestSendMessage_ConnectionRefused(t *testing.T) {
	service := NewService("http://localhost:1", "test-model", &http.Client{})

	_, err := service.SendMessage([]Message{{Role: "user", Content: "hi"}}, "")
	if err == nil {
		t.Fatal("expected error for connection refused")
	}
}
