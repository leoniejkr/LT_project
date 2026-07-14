package api

import (
	"backend/internal/patient"
	"bytes"
	"encoding/json"
	"io"
	"net/http"
)

type Handler struct {
	patientService *patient.Service
}

func NewHandler(patientService *patient.Service) *Handler {
	return &Handler{
		patientService: patientService,
	}
}

func (h *Handler) RegisterRoutes(router *http.ServeMux) {
	router.HandleFunc("POST /analysis", h.GetAnalysis)
	router.HandleFunc("DELETE /analysis", h.DeleteAnalysis)
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
			Reader: bytes.NewReader(buf),
			Name:   fh.Filename,
			Bytes:  buf,
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
		w.WriteHeader(http.StatusAccepted)
		json.NewEncoder(w).Encode(map[string]any{
			"status":  "partial",
			"patient": createdPatient,
			"analysis": map[string]any{
				"error": "Analysis failed: " + err.Error(),
			},
		})
		return
	}

	w.WriteHeader(http.StatusAccepted)
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
