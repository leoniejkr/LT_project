package analysis

import (
	"backend/internal/orthanc"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"image"
	"image/png"
	"net/http"
	"net/http/httptest"
	"testing"

	httpclient "backend/internal/http"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func testHeatmapPNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewNRGBA(image.Rect(0, 0, 4, 4))
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("failed to create test png: %v", err)
	}
	return buf.Bytes()
}

func setupServiceTest(t *testing.T, llmResponse ModelPredictionResponse) (*Service, *httptest.Server) {
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

	orthancServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"ID": "orthanc-heatmap-1"}`))
	}))

	llmClient := &LLMClient{client: httpclient.New(server.URL)}
	repo := NewRepository(db)
	orthancStore := orthanc.NewRepository(orthancServer.URL, "", "")
	svc := NewService(repo, llmClient, orthancStore)

	t.Cleanup(orthancServer.Close)

	return svc, server
}

func TestGetAnalysis_Success(t *testing.T) {
	llmResp := ModelPredictionResponse{
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
	llmResp := ModelPredictionResponse{
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
	if len(analysis.Predictions) != 1 {
		t.Fatalf("predictions length = %d, want 1", len(analysis.Predictions))
	}
	if analysis.Predictions[0].Class != "Effusion" {
		t.Errorf("prediction = %q, want %q", analysis.Predictions[0].Class, "Effusion")
	}
	if analysis.Predictions[0].Confidence != 0.85 {
		t.Errorf("confidence = %f, want 0.85", analysis.Predictions[0].Confidence)
	}
	if analysis.PatientID != 5 {
		t.Errorf("patient_id = %d, want 5", analysis.PatientID)
	}
}

func TestGetAnalysis_PersistsAllPredictions(t *testing.T) {
	llmResp := ModelPredictionResponse{
		Status: "success",
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
	if len(a.Predictions) != 2 {
		t.Fatalf("predictions length = %d, want 2", len(a.Predictions))
	}
	if a.Predictions[0].Class != "First" || a.Predictions[0].Reason != "Top prediction" {
		t.Errorf("first prediction = %+v, want class First with its reason", a.Predictions[0])
	}
	if a.Predictions[1].Class != "Second" || a.Predictions[1].Reason != "Second" {
		t.Errorf("second prediction = %+v, want class Second with its reason", a.Predictions[1])
	}
}

func TestGetAnalysis_EmptyPredictions(t *testing.T) {
	llmResp := ModelPredictionResponse{
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
	if len(a.Predictions) != 0 {
		t.Errorf("expected no predictions, got %d", len(a.Predictions))
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

	orthancStore := orthanc.NewRepository("http://localhost:1", "", "")
	llmClient := &LLMClient{client: httpclient.New(server.URL)}
	repo := NewRepository(db)
	svc := NewService(repo, llmClient, orthancStore)

	_, err := svc.GetAnalysis(1, map[string]string{}, nil, nil, "", "")
	if err == nil {
		t.Fatal("expected error when LLM service fails")
	}
}

func TestServiceDeletePatientAnalysis(t *testing.T) {
	llmResp := ModelPredictionResponse{
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
	llmResp := ModelPredictionResponse{
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

func TestGetAnalysis_StoresHeatmapsInOrthanc(t *testing.T) {
	heatmapPNG := testHeatmapPNG(t)
	llmResp := ModelPredictionResponse{
		Status: "success",
		Predictions: Predictions{
			{Class: "Pneumonia", Confidence: 0.92},
		},
		ImageResults: ImageResults{
			{
				Index:    0,
				Filename: "scan.png",
				Predictions: ImagePredictions{
					{Class: "Pneumonia", Confidence: 0.92, Heatmap: base64.StdEncoding.EncodeToString(heatmapPNG)},
				},
			},
		},
	}

	svc, server := setupServiceTest(t, llmResp)
	defer server.Close()

	result, err := svc.GetAnalysis(7, map[string]string{}, nil, nil, "", "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if got := result.ImageResults[0].Predictions[0].Heatmap; got == "" {
		t.Error("response should keep the base64 heatmap")
	}

	a, err := svc.repo.FindByPatientID(7)
	if err != nil {
		t.Fatalf("failed to find persisted analysis: %v", err)
	}
	pred := a.ImageResults[0].Predictions[0]
	if pred.OrthancID != "orthanc-heatmap-1" {
		t.Errorf("orthanc_id = %q, want %q", pred.OrthancID, "orthanc-heatmap-1")
	}
	if pred.Heatmap != "" {
		t.Error("persisted analysis should not keep the base64 heatmap when stored in orthanc")
	}
}
