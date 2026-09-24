package api

import (
	"backend/internal/analysis"
	"backend/internal/chat"
	"backend/internal/patient"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	httpSwagger "github.com/swaggo/http-swagger"
)

type Handler struct {
	patientService  *patient.Service
	chatService     *chat.Service
	analysisService *analysis.Service
}

func NewHandler(patientService *patient.Service, chatService *chat.Service, analysisService *analysis.Service) *Handler {
	return &Handler{
		patientService:  patientService,
		chatService:     chatService,
		analysisService: analysisService,
	}
}

func (h *Handler) RegisterRoutes(router *http.ServeMux) {
	router.HandleFunc("GET /health", h.HealthCheck)
	router.Handle("/swagger/", httpSwagger.WrapHandler)
	router.HandleFunc("POST /analysis", h.GetAnalysis)
	router.HandleFunc("DELETE /analysis", h.DeleteAnalysis)
	router.HandleFunc("GET /patients", h.ListPatients)
	router.HandleFunc("DELETE /patients/{id}", h.DeletePatient)
	router.HandleFunc("GET /patients/{id}/analysis", h.GetPatientAnalysis)
	router.HandleFunc("GET /patients/{id}/images/{imageID}", h.GetPatientImage)
	router.HandleFunc("GET /patients/{id}/export", h.ExportPatient)
	router.HandleFunc("GET /export", h.ExportAll)
	router.HandleFunc("POST /chat", h.Chat)
}

// Health godoc
// @Summary      Health check
// @Description  Returns OK if the server is running
// @Tags         health
// @Produce      plain
// @Success      200  {string}  string  "OK"
// @Router       /health [get]
func (h *Handler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintln(w, "OK")

}

// GetAnalysis godoc
// @Summary      Get AI analysis
// @Description  Upload patient data and X-Ray pictures and get analysis results back
// @Tags         analysis
// @Accept       multipart/form-data
// @Produce      json
// @Param        formData  formData  string  true  "Patient data as JSON (age, gender, symptoms, history)"
// @Param        image_files  formData  []file  true  "X-Ray PNG images"
// @Success      200  {object}  AnalysisResultResponse  "Successful analysis"
// @Failure      400  {object}  string  "Invalid request"
// @Failure      500  {object}  map[string]interface{}  "Analysis or server error"
// @Router       /analysis [post]
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

	classifierModel := r.FormValue("classifier_model")
	llmModel := r.FormValue("llm_model")

	createdPatient, err := h.patientService.CreatePatient(&p, files)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	analysisResp, err := h.analysisService.GetAnalysis(createdPatient.ID, createdPatient, imageBuffers, imageNames, classifierModel, llmModel)
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
	json.NewEncoder(w).Encode(AnalysisResultResponse{
		Status: "success", Patient: newPatientResponse(createdPatient), Analysis: newAnalysisResponseFromModel(analysisResp),
	})
}

// DeleteAnalysis godoc
// @Summary      Delete all patient data
// @Description  Deletes all patient data, analysis results, and associated images from all application databases
// @Tags         analysis
// @Produce      json
// @Success      200  {object}  map[string]string  "Deletion successful"
// @Failure      500  {object}  string  "Deletion failed"
// @Router       /analysis [delete]
func (h *Handler) DeleteAnalysis(w http.ResponseWriter, r *http.Request) {
	if err := h.patientService.DeleteAll(); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	if err := h.analysisService.DeleteAll(); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "deleted",
	})
}

func buildContextMessage(context map[string]any) (chat.Message, bool) {
	if len(context) == 0 {
		return chat.Message{}, false
	}
	payload, err := json.Marshal(context)
	if err != nil || len(payload) == 0 {
		return chat.Message{}, false
	}

	derived := riskCueMessage(context)
	return chat.Message{
		Role: chat.SystemRole,
		Content: "Known patient context for this conversation " +
			"(age, checked symptoms, medical history and risk factors, analysis findings). " +
			"The patient metadata below is CONFIRMED information about this patient and MUST be " +
			"treated as fact: every entry in the patient's history is a real condition, risk " +
			"factor, or exposure of this patient (for example, if \"Pregnancy\" is listed, the " +
			"patient IS pregnant). Never state that a high-risk factor such as pregnancy, infancy " +
			"or early childhood, advanced age, smoking, or immunosuppression does NOT apply to " +
			"this patient when it is listed in the history or in the derived cues. Always base " +
			"your answer on THIS patient's actual data first, then on general medical " +
			"knowledge:\n" + string(payload) + derived,
	}, true
}

// riskCueMessage derives explicit, easy-to-follow risk statements from the
// patient block, mirroring the analysis prompt in reason_generator.py. Small
// local LLMs often skim raw JSON, so the crucial facts are restated in plain
// language that cannot be ignored.
func riskCueMessage(context map[string]any) string {
	cues := []string{}
	if patient, ok := context["patient"].(map[string]any); ok {
		if age, ok := patient["age"].(float64); ok && age > 0 {
			switch {
			case age < 2:
				cues = append(cues, "the patient is an infant (under 2 years)")
			case age < 18:
				cues = append(cues, "the patient is a child or adolescent")
			case age >= 65:
				cues = append(cues, "the patient is an older adult (65+)")
			}
		}
		history := toStringSlice(patient["history"])
		joined := strings.ToLower(strings.Join(history, " "))
		if strings.Contains(joined, "pregnan") {
			cues = append(cues, "the patient is pregnant")
		}
		if strings.Contains(joined, "smok") {
			cues = append(cues, "the patient has a smoking/exposure history")
		}
	}
	if len(cues) == 0 {
		return ""
	}
	return "\n\nDerived patient risk cues (CONFIRMED): " + strings.Join(cues, "; ") + "."
}

// toStringSlice normalizes a JSON-decoded ([]any) or Go-typed ([]string)
// patient list field into a []string.
func toStringSlice(v any) []string {
	switch t := v.(type) {
	case []string:
		return t
	case []any:
		out := make([]string, 0, len(t))
		for _, e := range t {
			if s, ok := e.(string); ok {
				out = append(out, s)
			}
		}
		return out
	default:
		return nil
	}
}

// Chat godoc
// @Summary      Chat with medical AI
// @Description  Send a message to the medical AI assistant with patient context
// @Tags         chat
// @Accept       json
// @Produce      json
// @Param        request  body  ChatRequest  true  "Chat request with message, history, and context"
// @Success      200  {object}  map[string]string  "AI reply"
// @Failure      400  {object}  string  "Invalid request or missing message"
// @Failure      502  {object}  map[string]string  "Chat service error"
// @Router       /chat [post]
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

	messages := []chat.Message{{Role: chat.SystemRole}}
	if contextMsg, ok := buildContextMessage(req.Context); ok {
		messages = append(messages, contextMsg)
	}
	for _, m := range req.History {
		if (m.Role == chat.UserRole) || (m.Role == chat.AssistantRole) {
			messages = append(messages, m)
		}
	}

	last := len(messages) - 1
	if (last < 1 || messages[last].Role != chat.UserRole) || (messages[last].Content != req.Message) {
		messages = append(messages, chat.Message{Role: chat.UserRole, Content: req.Message})
	}

	reply, err := h.chatService.SendMessage(messages, req.Model)
	if err != nil {
		w.WriteHeader(http.StatusBadGateway)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Chat failed: " + err.Error(),
		})
		return
	}

	json.NewEncoder(w).Encode(map[string]string{"reply": reply})
}
