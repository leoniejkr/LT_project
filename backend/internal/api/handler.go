package api

import (
	"backend/internal/chat"
	"backend/internal/patient"
	"encoding/json"
	"io"
	"net/http"
	"strings"
)

type Handler struct {
	patientService *patient.Service
	chatClient     *chat.Client
}

func NewHandler(patientService *patient.Service, chatClient *chat.Client) *Handler {
	return &Handler{
		patientService: patientService,
		chatClient:     chatClient,
	}
}

func (h *Handler) RegisterRoutes(router *http.ServeMux) {
	router.HandleFunc("POST /analysis", h.GetAnalysis)
	router.HandleFunc("DELETE /analysis", h.DeleteAnalysis)
	router.HandleFunc("POST /chat", h.Chat)
}

func (h *Handler) GetAnalysis(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(50 << 20); err != nil {
		http.Error(w, "Unable to parse multipart form", http.StatusBadRequest)
		return
	}

	formData := r.FormValue("formData")
	if formData == "" {
		http.Error(w, "Missing formData", http.StatusBadRequest)
		return
	}

	var p patient.Patient
	if err := json.Unmarshal([]byte(formData), &p); err != nil {
		http.Error(w, "Invalid JSON in formData", http.StatusBadRequest)
		return
	}

	var files []patient.FileInput
	var imageBuffers [][]byte
	var imageNames []string

	fileHeaders := r.MultipartForm.File["image_files"]
	for _, fh := range fileHeaders {
		if !strings.HasSuffix(strings.ToLower(fh.Filename), ".png") {
			http.Error(w, "Only PNG files are allowed: "+fh.Filename, http.StatusBadRequest)
			return
		}

		f, err := fh.Open()
		if err != nil {
			http.Error(w, "Failed to read uploaded file", http.StatusInternalServerError)
			return
		}
		defer f.Close()

		buf, err := io.ReadAll(f)
		if err != nil {
			http.Error(w, "Failed to read file content", http.StatusInternalServerError)
			return
		}

		files = append(files, patient.FileInput{
			Name:  fh.Filename,
			Bytes: buf,
		})
		imageBuffers = append(imageBuffers, buf)
		imageNames = append(imageNames, fh.Filename)
	}

	createdPatient, err := h.patientService.CreatePatient(&p, files)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	analysisResp, err := h.patientService.GetAnalysis(createdPatient.ID, createdPatient, imageBuffers, imageNames)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]any{
			"status":  "error",
			"patient": createdPatient,
			"analysis": map[string]any{
				"error": "Analysis failed: " + err.Error(),
			},
		})
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]any{
		"status":   "success",
		"patient":  createdPatient,
		"analysis": analysisResp,
	})
}

func (h *Handler) DeleteAnalysis(w http.ResponseWriter, r *http.Request) {
	if err := h.patientService.DeleteAllData(); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "deleted",
	})
}

const chatSystemPrompt = `You are a medical AI assistant helping clinicians understand chest X-ray analysis results.
Answer questions about diagnoses, confidence scores and findings clearly and concisely.
Use the patient context provided in this conversation (symptoms, medical history, risk factors)
when answering questions about the patient.
If you are unsure, say so. Always recommend consulting a radiologist for final decisions.`

type ChatRequest struct {
	Message string         `json:"message"`
	History []chat.Message `json:"history"`
	Context map[string]any `json:"context,omitempty"`
}

// buildContextMessage renders the client-supplied patient context as an
// additional system message so the model can reason about it.
func buildContextMessage(context map[string]any) (chat.Message, bool) {
	if len(context) == 0 {
		return chat.Message{}, false
	}
	payload, err := json.Marshal(context)
	if err != nil || len(payload) == 0 {
		return chat.Message{}, false
	}
	return chat.Message{
		Role: "system",
		Content: "Known patient context for this conversation " +
			"(age, checked symptoms, medical history and risk factors, analysis findings). " +
			"Use it when answering questions about this patient:\n" + string(payload),
	}, true
}

func (h *Handler) Chat(w http.ResponseWriter, r *http.Request) {
	var req ChatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON body", http.StatusBadRequest)
		return
	}

	if req.Message == "" {
		http.Error(w, "Missing message", http.StatusBadRequest)
		return
	}

	messages := []chat.Message{{Role: "system", Content: chatSystemPrompt}}
	if contextMsg, ok := buildContextMessage(req.Context); ok {
		messages = append(messages, contextMsg)
	}
	for _, m := range req.History {
		if m.Role == "user" || m.Role == "assistant" {
			messages = append(messages, m)
		}
	}

	last := len(messages) - 1
	if last < 1 || messages[last].Role != "user" || messages[last].Content != req.Message {
		messages = append(messages, chat.Message{Role: "user", Content: req.Message})
	}

	reply, err := h.chatClient.SendMessage(messages)
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Chat failed: " + err.Error(),
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]string{"reply": reply})
}
