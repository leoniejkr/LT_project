package analysis

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	httpclient "backend/internal/http"
	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupServiceTest(t *testing.T, llmResponse PredictionResponse) (*Service, *httptest.Server) {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open test db: %v", err)
	}
	db.AutoMigrate(&Analysis{})

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(llmResponse)
	}))

	llmClient := &LLMClient{client: httpclient.New(server.URL)}
	repo := NewRepository(db)
	svc := NewService(repo, llmClient)

	return svc, server
}

func TestGetAnalysis_Success(t *testing.T) {
	llmResp := PredictionResponse{
		Status:       "success",
		ModelVersion: "v1.0",
		Predictions: Predictions{
			{Class: "Pneumonia", Confidence: 0.92, Reason: "Strong evidence"},
		},
	}

	svc, server := setupServiceTest(t, llmResp)
	defer server.Close()

	patientData := map[string]string{"id": "1"}
	result, err := svc.GetAnalysis(1, patientData, nil, nil, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Status != "success" {
		t.Errorf("status = %q, want %q", result.Status, "success")
	}
	if len(result.Predictions) != 1 {
		t.Fatalf("expected 1 prediction, got %d", len(result.Predictions))
	}
}

func TestGetAnalysis_PersistsToDB(t *testing.T) {
	llmResp := PredictionResponse{
		Status:       "success",
		ModelVersion: "v1.0",
		Predictions: Predictions{
			{Class: "Effusion", Confidence: 0.85, Reason: "Fluid detected"},
		},
	}

	svc, server := setupServiceTest(t, llmResp)
	defer server.Close()

	_, err := svc.GetAnalysis(5, map[string]string{}, nil, nil, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Verify it was persisted
	analysis, err := svc.repo.FindByPatientID(5)
	if err != nil {
		t.Fatalf("failed to find persisted analysis: %v", err)
	}
	if analysis.Prediction != "Effusion" {
		t.Errorf("prediction = %q, want %q", analysis.Prediction, "Effusion")
	}
	if analysis.Confidence != 0.85 {
		t.Errorf("confidence = %f, want 0.85", analysis.Confidence)
	}
	if analysis.PatientID != 5 {
		t.Errorf("patient_id = %d, want 5", analysis.PatientID)
	}
}

func TestGetAnalysis_PersistsTopPrediction(t *testing.T) {
	llmResp := PredictionResponse{
		Status:      "success",
		Predictions: Predictions{
			{Class: "First", Confidence: 0.95, Reason: "Top prediction"},
			{Class: "Second", Confidence: 0.70, Reason: "Second"},
		},
	}

	svc, server := setupServiceTest(t, llmResp)
	defer server.Close()

	_, err := svc.GetAnalysis(1, map[string]string{}, nil, nil, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	a, _ := svc.repo.FindByPatientID(1)
	if a.Prediction != "First" {
		t.Errorf("top prediction = %q, want %q", a.Prediction, "First")
	}
	if a.ConfidenceReason != "Top prediction" {
		t.Errorf("confidence reason = %q, want %q", a.ConfidenceReason, "Top prediction")
	}
}

func TestGetAnalysis_EmptyPredictions(t *testing.T) {
	llmResp := PredictionResponse{
		Status:      "success",
		Predictions: Predictions{},
	}

	svc, server := setupServiceTest(t, llmResp)
	defer server.Close()

	_, err := svc.GetAnalysis(1, map[string]string{}, nil, nil, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	a, _ := svc.repo.FindByPatientID(1)
	if a.Prediction != "" {
		t.Errorf("expected empty prediction, got %q", a.Prediction)
	}
}

func TestGetAnalysis_LLMError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("service unavailable"))
	}))
	defer server.Close()

	db, _ := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	db.AutoMigrate(&Analysis{})

	llmClient := &LLMClient{client: httpclient.New(server.URL)}
	repo := NewRepository(db)
	svc := NewService(repo, llmClient)

	_, err := svc.GetAnalysis(1, map[string]string{}, nil, nil, "", "")
	if err == nil {
		t.Fatal("expected error when LLM service fails")
	}
}

func TestServiceDeletePatientAnalysis(t *testing.T) {
	llmResp := PredictionResponse{
		Status:      "success",
		Predictions: Predictions{{Class: "X", Confidence: 0.9}},
	}

	svc, server := setupServiceTest(t, llmResp)
	defer server.Close()

	svc.GetAnalysis(1, map[string]string{}, nil, nil, "", "")

	if err := svc.DeletePatientAnalysis(1); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	_, err := svc.repo.FindByPatientID(1)
	if err == nil {
		t.Fatal("expected error after deletion")
	}
}

func TestPersistAnalysis_PreservesAllFields(t *testing.T) {
	llmResp := PredictionResponse{
		Status:       "success",
		ModelVersion: "v2.0",
		Predictions: Predictions{
			{Class: "Pneumonia", Confidence: 0.99, Reason: "Clear"},
		},
		ImageResults: ImageResults{
			{
				Index:    0,
				Filename: "scan.png",
				Predictions: ImagePredictions{
					{Class: "Pneumonia", Confidence: 0.99, Heatmap: "abc123"},
				},
			},
		},
	}

	svc, server := setupServiceTest(t, llmResp)
	defer server.Close()

	_, err := svc.GetAnalysis(10, map[string]string{}, nil, nil, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	a, _ := svc.repo.FindByPatientID(10)
	if a.ModelVersion != "v2.0" {
		t.Errorf("model_version = %q, want %q", a.ModelVersion, "v2.0")
	}
	if len(a.ImageResults) != 1 {
		t.Fatalf("expected 1 image result, got %d", len(a.ImageResults))
	}
	if a.ImageResults[0].Filename != "scan.png" {
		t.Errorf("filename = %q, want %q", a.ImageResults[0].Filename, "scan.png")
	}
}
