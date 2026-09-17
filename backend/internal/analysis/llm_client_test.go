package analysis

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	httpclient "backend/internal/http"
)

func TestGetPrediction_Success(t *testing.T) {
	expected := ModelPredictionResponse{
		Status:       "success",
		ModelVersion: "v1.0",
		Predictions: Predictions{
			{Class: "Pneumonia", Confidence: 0.92, Reason: "Test reason"},
		},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/predict" {
			t.Errorf("expected /predict, got %s", r.URL.Path)
		}
		if !strings.HasPrefix(r.Header.Get("Content-Type"), "multipart/form-data") {
			t.Errorf("expected multipart content type, got %s", r.Header.Get("Content-Type"))
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expected)
	}))
	defer server.Close()

	client := &LLMClient{client: httpclient.New(server.URL)}

	patientData := map[string]string{"id": "1"}
	imageBuffers := [][]byte{[]byte("fake-png-data")}
	imageNames := []string{"test.png"}

	result, err := client.GetPrediction(patientData, imageBuffers, imageNames, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Status != expected.Status {
		t.Errorf("status = %q, want %q", result.Status, expected.Status)
	}
	if result.ModelVersion != expected.ModelVersion {
		t.Errorf("model_version = %q, want %q", result.ModelVersion, expected.ModelVersion)
	}
	if len(result.Predictions) != 1 {
		t.Fatalf("predictions len = %d, want 1", len(result.Predictions))
	}
	if result.Predictions[0].Class != "Pneumonia" {
		t.Errorf("prediction class = %q, want %q", result.Predictions[0].Class, "Pneumonia")
	}
	if result.Predictions[0].Confidence != 0.92 {
		t.Errorf("prediction confidence = %f, want 0.92", result.Predictions[0].Confidence)
	}
}

func TestGetPrediction_NoImages(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(ModelPredictionResponse{Status: "success"})
	}))
	defer server.Close()

	client := &LLMClient{client: httpclient.New(server.URL)}

	result, err := client.GetPrediction(map[string]string{"id": "1"}, nil, nil, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Status != "success" {
		t.Errorf("status = %q, want %q", result.Status, "success")
	}
}

func TestGetPrediction_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("internal error"))
	}))
	defer server.Close()

	client := &LLMClient{client: httpclient.New(server.URL)}

	_, err := client.GetPrediction(map[string]string{"id": "1"}, nil, nil, "", "")
	if err == nil {
		t.Fatal("expected error for server error response")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Errorf("error should contain status code 500, got: %v", err)
	}
}

func TestGetPrediction_InvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte("not json"))
	}))
	defer server.Close()

	client := &LLMClient{client: httpclient.New(server.URL)}

	_, err := client.GetPrediction(map[string]string{"id": "1"}, nil, nil, "", "")
	if err == nil {
		t.Fatal("expected error for invalid JSON response")
	}
	if !strings.Contains(err.Error(), "decode") {
		t.Errorf("error should mention decode failure, got: %v", err)
	}
}

func TestGetPrediction_ConnectionRefused(t *testing.T) {
	client := &LLMClient{client: httpclient.New("http://localhost:1")}

	_, err := client.GetPrediction(map[string]string{"id": "1"}, nil, nil, "", "")
	if err == nil {
		t.Fatal("expected error for connection refused")
	}
}

func TestGetPrediction_MarshalError(t *testing.T) {
	client := &LLMClient{client: httpclient.New("http://localhost:1")}

	// channels cannot be marshaled to JSON
	ch := make(chan int)
	_, err := client.GetPrediction(ch, nil, nil, "", "")
	if err == nil {
		t.Fatal("expected error for marshal failure")
	}
	if !strings.Contains(err.Error(), "marshal") {
		t.Errorf("error should mention marshal, got: %v", err)
	}
}

func TestGetPrediction_MultipleImages(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := r.ParseMultipartForm(10 << 20); err != nil {
			t.Errorf("failed to parse form: %v", err)
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		files := r.MultipartForm.File["image_files"]
		if len(files) != 2 {
			t.Errorf("expected 2 files, got %d", len(files))
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(ModelPredictionResponse{Status: "success"})
	}))
	defer server.Close()

	client := &LLMClient{client: httpclient.New(server.URL)}

	buffers := [][]byte{[]byte("img1"), []byte("img2")}
	names := []string{"a.png", "b.png"}

	result, err := client.GetPrediction(map[string]string{}, buffers, names, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Status != "success" {
		t.Errorf("status = %q, want %q", result.Status, "success")
	}
}
