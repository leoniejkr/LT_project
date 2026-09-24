package api

import (
	"backend/internal/analysis"
	"backend/internal/chat"
	"backend/internal/orthanc"
	"backend/internal/patient"
	"bytes"
	"encoding/json"
	"fmt"
	"image"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func testPNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewGray(image.Rect(0, 0, 4, 4))
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("failed to create test png: %v", err)
	}
	return buf.Bytes()
}

func setupHandler(t *testing.T, llmHandler http.HandlerFunc) (*Handler, *httptest.Server, *httptest.Server) {
	t.Helper()

	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open test db: %v", err)
	}
	db.AutoMigrate(&patient.Patient{}, &analysis.Analysis{})

	llmServer := httptest.NewServer(llmHandler)
	t.Setenv("MODELLING_URL", llmServer.URL)

	orthancServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet && r.URL.Path == "/patients" {
			w.Write([]byte(`[]`))
			return
		}
		if r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/instances/") {
			w.Header().Set("Content-Type", "image/png")
			w.Write([]byte("preview-image"))
			return
		}
		w.Write([]byte(`{"ID": "orthanc-1"}`))
	}))

	llmClient := analysis.NewLLMClient()
	analysisRepo := analysis.NewRepository(db)

	orthancRepo := orthanc.NewRepository(orthancServer.URL, "", "")
	analysisSvc := analysis.NewService(analysisRepo, llmClient, orthancRepo)

	patientRepo := patient.NewRepository(db)
	patientSvc := patient.NewService(patientRepo, orthancRepo)
	chatSvc := chat.NewService("", "default-model", &http.Client{})

	handler := NewHandler(patientSvc, chatSvc, analysisSvc)
	return handler, llmServer, orthancServer
}

func defaultLLMHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(analysis.ModelPredictionResponse{
			Status:       "success",
			ModelVersion: "v1.0",
			Predictions: analysis.Predictions{
				{Class: "Pneumonia", Confidence: 0.92, Reason: "Test"},
			},
		})
	}
}

func TestGetAnalysis_Success(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)

	patientData := `{"age":62,"gender":"Male","symptoms":["Shortness of breath (dyspnea)"],"history":["Smoking tobacco / cigarettes"]}`
	writer.WriteField("formData", patientData)

	part, _ := writer.CreateFormFile("image_files", "xray.png")
	part.Write(testPNG(t))
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", w.Code, http.StatusOK)
	}

	var resp map[string]any
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["status"] != "success" {
		t.Errorf("response status = %v, want success", resp["status"])
	}
}

func TestGetAnalysis_MissingFormData(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("other_field", "value")
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want %d", w.Code, http.StatusBadRequest)
	}
	if !strings.Contains(w.Body.String(), "Missing formData") {
		t.Errorf("body should mention missing formData, got: %s", w.Body.String())
	}
}

func TestGetAnalysis_InvalidJSON(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", "not valid json")
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want %d", w.Code, http.StatusBadRequest)
	}
	if !strings.Contains(w.Body.String(), "Invalid JSON") {
		t.Errorf("body should mention invalid JSON, got: %s", w.Body.String())
	}
}

func TestGetAnalysis_NonPNGFile(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":30,"gender":"Male"}`)

	part, _ := writer.CreateFormFile("image_files", "scan.jpg")
	part.Write([]byte("fake-jpg-data"))
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want %d", w.Code, http.StatusBadRequest)
	}
	if !strings.Contains(w.Body.String(), "Only PNG") {
		t.Errorf("body should mention PNG only, got: %s", w.Body.String())
	}
}

func TestGetAnalysis_NoFiles(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":45,"gender":"Female"}`)
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", w.Code, http.StatusOK)
	}
}

func TestDeleteAnalysis_Success(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	req := httptest.NewRequest(http.MethodDelete, "/analysis", nil)
	w := httptest.NewRecorder()

	handler.DeleteAnalysis(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", w.Code, http.StatusOK)
	}

	var resp map[string]string
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["status"] != "deleted" {
		t.Errorf("response status = %v, want deleted", resp["status"])
	}
}

func TestDeleteAnalysis_EmptyDB(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	req := httptest.NewRequest(http.MethodDelete, "/analysis", nil)
	w := httptest.NewRecorder()

	handler.DeleteAnalysis(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d on empty db", w.Code, http.StatusOK)
	}
}

func TestGetAnalysis_MultipleFiles(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":50,"gender":"Male"}`)

	for _, name := range []string{"a.png", "b.png", "c.png"} {
		part, _ := writer.CreateFormFile("image_files", name)
		part.Write(testPNG(t))
	}
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d", w.Code, http.StatusOK)
	}
}

func TestGetAnalysis_LLMFailure(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("model down"))
	})
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":60,"gender":"Male"}`)
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("status = %d, want %d (LLM failure)", w.Code, http.StatusInternalServerError)
	}

	var resp map[string]any
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["status"] != "error" {
		t.Errorf("response status = %v, want error", resp["status"])
	}
}

func TestRegisterRoutes(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	router := http.NewServeMux()
	handler.RegisterRoutes(router)

	postReq := httptest.NewRequest(http.MethodPost, "/analysis", nil)
	postW := httptest.NewRecorder()
	router.ServeHTTP(postW, postReq)
	if postW.Code == http.StatusNotFound {
		t.Error("POST /analysis route not registered")
	}

	deleteReq := httptest.NewRequest(http.MethodDelete, "/analysis", nil)
	deleteW := httptest.NewRecorder()
	router.ServeHTTP(deleteW, deleteReq)
	if deleteW.Code == http.StatusNotFound {
		t.Error("DELETE /analysis route not registered")
	}
}

func TestGetAnalysis_CaseInsensitivePNG(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":25,"gender":"Male"}`)

	part, _ := writer.CreateFormFile("image_files", "XRAY.PNG")
	part.Write(testPNG(t))
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d (uppercase .PNG should be allowed)", w.Code, http.StatusOK)
	}
}

func TestGetAnalysis_MissingImageFiles(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":40,"gender":"Female"}`)
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()

	handler.GetAnalysis(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d (no image files is ok)", w.Code, http.StatusOK)
	}
}

func TestDeleteAnalysis_CleansUpData(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	for _, age := range []int{55, 72} {
		body := &bytes.Buffer{}
		writer := multipart.NewWriter(body)
		writer.WriteField("formData", fmt.Sprintf(`{"age":%d,"gender":"Male"}`, age))
		writer.Close()
		req := httptest.NewRequest(http.MethodPost, "/analysis", body)
		req.Header.Set("Content-Type", writer.FormDataContentType())
		w := httptest.NewRecorder()
		handler.GetAnalysis(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("create status = %d, want 200", w.Code)
		}
	}

	deleteReq := httptest.NewRequest(http.MethodDelete, "/analysis", nil)
	deleteW := httptest.NewRecorder()
	handler.DeleteAnalysis(deleteW, deleteReq)

	if deleteW.Code != http.StatusOK {
		t.Errorf("delete status = %d, want %d", deleteW.Code, http.StatusOK)
	}

	listW := httptest.NewRecorder()
	handler.ListPatients(listW, httptest.NewRequest(http.MethodGet, "/patients", nil))
	var patients []PatientSummary
	if err := json.NewDecoder(listW.Body).Decode(&patients); err != nil {
		t.Fatalf("decode history: %v", err)
	}
	if len(patients) != 0 {
		t.Errorf("history = %#v, want no patients", patients)
	}
}

func TestHistoryEndpoints_ReturnPersistedAnalysis(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	// Create a completed analysis first, just as the upload page does.
	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":55,"gender":"Male"}`)
	part, _ := writer.CreateFormFile("image_files", "xray.png")
	part.Write(testPNG(t))
	writer.Close()
	postReq := httptest.NewRequest(http.MethodPost, "/analysis", body)
	postReq.Header.Set("Content-Type", writer.FormDataContentType())
	postW := httptest.NewRecorder()
	handler.GetAnalysis(postW, postReq)
	if postW.Code != http.StatusOK {
		t.Fatalf("analysis status = %d, want 200", postW.Code)
	}

	router := http.NewServeMux()
	handler.RegisterRoutes(router)

	listW := httptest.NewRecorder()
	router.ServeHTTP(listW, httptest.NewRequest(http.MethodGet, "/patients", nil))
	if listW.Code != http.StatusOK {
		t.Fatalf("history status = %d, want 200", listW.Code)
	}
	var patients []struct {
		ID     uint   `json:"id"`
		Age    uint   `json:"age"`
		Gender string `json:"gender"`
	}
	if err := json.NewDecoder(listW.Body).Decode(&patients); err != nil {
		t.Fatalf("decode history: %v", err)
	}
	if len(patients) != 1 || patients[0].Age != 55 || patients[0].Gender != "Male" {
		t.Errorf("history = %#v, want one completed patient", patients)
	}

	detailW := httptest.NewRecorder()
	router.ServeHTTP(detailW, httptest.NewRequest(http.MethodGet, "/patients/1/analysis", nil))
	if detailW.Code != http.StatusOK {
		t.Fatalf("detail status = %d, want 200", detailW.Code)
	}
	var detail struct {
		Patient  patient.Patient  `json:"patient"`
		Analysis AnalysisResponse `json:"analysis"`
	}
	if err := json.NewDecoder(detailW.Body).Decode(&detail); err != nil {
		t.Fatalf("decode detail: %v", err)
	}
	if detail.Patient.ID != 1 || len(detail.Analysis.Predictions) != 1 {
		t.Errorf("unexpected historic detail: %#v", detail)
	}

	imageW := httptest.NewRecorder()
	router.ServeHTTP(imageW, httptest.NewRequest(http.MethodGet, "/patients/1/images/orthanc-1", nil))
	if imageW.Code != http.StatusOK {
		t.Fatalf("image status = %d, want 200", imageW.Code)
	}
	if imageW.Header().Get("Content-Type") != "image/png" {
		t.Errorf("content type = %q, want image/png", imageW.Header().Get("Content-Type"))
	}
	if imageW.Body.String() != "preview-image" {
		t.Errorf("image body = %q, want preview-image", imageW.Body.String())
	}
}

func TestHistoryEndpoints_RejectUnknownPatient(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()
	router := http.NewServeMux()
	handler.RegisterRoutes(router)

	w := httptest.NewRecorder()
	router.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/patients/999/analysis", nil))
	if w.Code != http.StatusNotFound {
		t.Errorf("status = %d, want 404", w.Code)
	}
}

func TestDeletePatient_RemovesOnlySelectedHistoryRow(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	for _, age := range []int{41, 67} {
		body := &bytes.Buffer{}
		writer := multipart.NewWriter(body)
		writer.WriteField("formData", fmt.Sprintf(`{"age":%d,"gender":"Male"}`, age))
		writer.Close()
		req := httptest.NewRequest(http.MethodPost, "/analysis", body)
		req.Header.Set("Content-Type", writer.FormDataContentType())
		w := httptest.NewRecorder()
		handler.GetAnalysis(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("create status = %d, want 200", w.Code)
		}
	}

	router := http.NewServeMux()
	handler.RegisterRoutes(router)
	deleteW := httptest.NewRecorder()
	router.ServeHTTP(deleteW, httptest.NewRequest(http.MethodDelete, "/patients/1", nil))
	if deleteW.Code != http.StatusNoContent {
		t.Fatalf("delete status = %d, want 204: %s", deleteW.Code, deleteW.Body.String())
	}

	listW := httptest.NewRecorder()
	router.ServeHTTP(listW, httptest.NewRequest(http.MethodGet, "/patients", nil))
	var patients []PatientSummary
	if err := json.NewDecoder(listW.Body).Decode(&patients); err != nil {
		t.Fatalf("decode history: %v", err)
	}
	if len(patients) != 1 || patients[0].ID != 2 {
		t.Errorf("history = %#v, want only patient 2", patients)
	}
}

func TestDeletePatient_RejectsInvalidAndUnknownID(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()
	router := http.NewServeMux()
	handler.RegisterRoutes(router)

	for path, want := range map[string]int{
		"/patients/not-a-number": http.StatusBadRequest,
		"/patients/999":          http.StatusNotFound,
	} {
		w := httptest.NewRecorder()
		router.ServeHTTP(w, httptest.NewRequest(http.MethodDelete, path, nil))
		if w.Code != want {
			t.Errorf("DELETE %s status = %d, want %d", path, w.Code, want)
		}
	}
}

func setupOllama(t *testing.T, handler func(messages []map[string]string) (string, int)) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Model    string              `json:"model"`
			Messages []map[string]string `json:"messages"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("failed to decode ollama request: %v", err)
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		reply, status := handler(req.Messages)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		json.NewEncoder(w).Encode(map[string]any{
			"message": map[string]string{"role": "assistant", "content": reply},
		})
	}))
}

func TestChat_Success(t *testing.T) {
	var receivedMessages []map[string]string
	ollamaSrv := setupOllama(t, func(messages []map[string]string) (string, int) {
		receivedMessages = messages
		return "Test reply", http.StatusOK
	})
	defer ollamaSrv.Close()
	t.Setenv("OLLAMA_URL", ollamaSrv.URL)

	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := `{"message": "What does the finding mean?", "history": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]}`
	req := httptest.NewRequest(http.MethodPost, "/chat", strings.NewReader(body))
	w := httptest.NewRecorder()

	handler.Chat(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d, body: %s", w.Code, http.StatusOK, w.Body.String())
	}

	var resp map[string]string
	json.NewDecoder(w.Body).Decode(&resp)
	if resp["reply"] != "Test reply" {
		t.Errorf("reply = %v, want 'Test reply'", resp["reply"])
	}

	if len(receivedMessages) == 0 || receivedMessages[0]["role"] != "system" {
		t.Error("expected system prompt as first message")
	}
	last := receivedMessages[len(receivedMessages)-1]
	if last["role"] != "user" || last["content"] != "What does the finding mean?" {
		t.Errorf("last message = %v/%v, want user/'What does the finding mean?'", last["role"], last["content"])
	}
}

func TestChat_WithContext(t *testing.T) {
	var receivedMessages []map[string]string
	ollamaSrv := setupOllama(t, func(messages []map[string]string) (string, int) {
		receivedMessages = messages
		return "Test reply", http.StatusOK
	})
	defer ollamaSrv.Close()
	t.Setenv("OLLAMA_URL", ollamaSrv.URL)

	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := `{"message": "What symptoms do I have?", "context": {"patient": {"age": 62, "symptoms": ["Fever (up to 105°F / 40°C)", "Shortness of breath (dyspnea)"], "history": ["Smoking tobacco / cigarettes"]}}}`
	req := httptest.NewRequest(http.MethodPost, "/chat", strings.NewReader(body))
	w := httptest.NewRecorder()

	handler.Chat(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d, body: %s", w.Code, http.StatusOK, w.Body.String())
	}

	foundContext := false
	for _, m := range receivedMessages {
		if m["role"] == "system" &&
			strings.Contains(m["content"], "Fever (up to 105°F / 40°C)") &&
			strings.Contains(m["content"], "Smoking tobacco / cigarettes") {
			foundContext = true
		}
	}
	if !foundContext {
		t.Error("expected patient context (symptoms and history) in a system message sent to Ollama")
	}
}

func TestChat_WithPregnancyContextDerivesPregnancy(t *testing.T) {
	var receivedMessages []map[string]string
	ollamaSrv := setupOllama(t, func(messages []map[string]string) (string, int) {
		receivedMessages = messages
		return "Test reply", http.StatusOK
	})
	defer ollamaSrv.Close()
	t.Setenv("OLLAMA_URL", ollamaSrv.URL)

	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	body := `{"message": "Am I at risk for severe Covid?", "context": {"patient": {"age": 45, "gender": "Female", "symptoms": [], "history": ["Pregnancy (including repeat pregnancies)"]}}}`
	req := httptest.NewRequest(http.MethodPost, "/chat", strings.NewReader(body))
	w := httptest.NewRecorder()

	handler.Chat(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("status = %d, want %d, body: %s", w.Code, http.StatusOK, w.Body.String())
	}

	var systemContent string
	for _, m := range receivedMessages {
		if m["role"] == "system" {
			systemContent = m["content"]
		}
	}

	if systemContent == "" {
		t.Fatal("expected a system message sent to Ollama")
	}
	if !strings.Contains(systemContent, "Pregnancy (including repeat pregnancies)") {
		t.Error("expected the submitted pregnancy history entry in the patient context")
	}
	if !strings.Contains(systemContent, "the patient is pregnant") {
		t.Error("expected a derived 'the patient is pregnant' cue in the system message")
	}
	if !strings.Contains(systemContent, "MUST be treated as fact") {
		t.Error("expected the system message to mark patient metadata as confirmed facts")
	}
}

func TestChat_MissingMessage(t *testing.T) {
	ollamaSrv := setupOllama(t, func(messages []map[string]string) (string, int) {
		return "", http.StatusOK
	})
	defer ollamaSrv.Close()
	t.Setenv("OLLAMA_URL", ollamaSrv.URL)

	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	req := httptest.NewRequest(http.MethodPost, "/chat", strings.NewReader(`{"history": []}`))
	w := httptest.NewRecorder()

	handler.Chat(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want %d", w.Code, http.StatusBadRequest)
	}
}

func TestChat_InvalidJSON(t *testing.T) {
	ollamaSrv := setupOllama(t, func(messages []map[string]string) (string, int) {
		return "", http.StatusOK
	})
	defer ollamaSrv.Close()
	t.Setenv("OLLAMA_URL", ollamaSrv.URL)

	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	for _, body := range []string{
		"not json",
		`{"message":"What is my risk?","context":{"patient":{"history":["Smoking",42]}}}`,
	} {
		req := httptest.NewRequest(http.MethodPost, "/chat", strings.NewReader(body))
		w := httptest.NewRecorder()

		handler.Chat(w, req)

		if w.Code != http.StatusBadRequest {
			t.Errorf("body = %q: status = %d, want %d", body, w.Code, http.StatusBadRequest)
		}
	}
}

func TestChat_OllamaFailure(t *testing.T) {
	ollamaSrv := setupOllama(t, func(messages []map[string]string) (string, int) {
		return "model overloaded", http.StatusInternalServerError
	})
	defer ollamaSrv.Close()
	t.Setenv("OLLAMA_URL", ollamaSrv.URL)

	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	req := httptest.NewRequest(http.MethodPost, "/chat", strings.NewReader(`{"message": "hi"}`))
	w := httptest.NewRecorder()

	handler.Chat(w, req)

	if w.Code != http.StatusBadGateway {
		t.Errorf("status = %d, want %d", w.Code, http.StatusBadGateway)
	}
}
