package api

import (
	"backend/internal/analysis"
	"backend/internal/chat"
	"backend/internal/orthanc"
	"backend/internal/patient"
	"bytes"
	"encoding/json"
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
		w.Write([]byte(`{"ID": "orthanc-1"}`))
	}))

	llmClient := analysis.NewLLMClient()
	analysisRepo := analysis.NewRepository(db)
	analysisSvc := analysis.NewService(analysisRepo, llmClient)

	orthancRepo := orthanc.NewRepository(orthancServer.URL, "", "")
	patientRepo := patient.NewRepository(db)
	patientSvc := patient.NewService(patientRepo, analysisSvc, orthancRepo)

	handler := NewHandler(patientSvc, chat.NewClient())
	return handler, llmServer, orthancServer
}

func defaultLLMHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(analysis.PredictionResponse{
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

	patientData := `{"age":62,"gender":"Male","knownIllnesses":["Covid19"],"symptoms":["Cough"]}`
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

	body := &bytes.Buffer{}
	writer := multipart.NewWriter(body)
	writer.WriteField("formData", `{"age":55,"gender":"Male"}`)
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/analysis", body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	w := httptest.NewRecorder()
	handler.GetAnalysis(w, req)

	deleteReq := httptest.NewRequest(http.MethodDelete, "/analysis", nil)
	deleteW := httptest.NewRecorder()
	handler.DeleteAnalysis(deleteW, deleteReq)

	if deleteW.Code != http.StatusOK {
		t.Errorf("delete status = %d, want %d", deleteW.Code, http.StatusOK)
	}
}

func setupOllama(t *testing.T, handler func(messages []map[string]string) (string, int)) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Model    string                `json:"model"`
			Messages []map[string]string   `json:"messages"`
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

	req := httptest.NewRequest(http.MethodPost, "/chat", strings.NewReader("not json"))
	w := httptest.NewRecorder()

	handler.Chat(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("status = %d, want %d", w.Code, http.StatusBadRequest)
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
