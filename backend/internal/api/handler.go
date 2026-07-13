package api

import (
	"backend/internal/analysis"
	"backend/internal/patient"
	"encoding/json"
	"net/http"
)

type Handler struct {
	patientService  *patient.Service
	analysisService *analysis.Service
}

func NewHandler(patientService *patient.Service, analysisService *analysis.Service) *Handler {
	return &Handler{
		patientService:  patientService,
		analysisService: analysisService,
	}
}

func (h *Handler) RegisterRoutes(router *http.ServeMux) {
	router.HandleFunc("POST /analysis", h.GetAnalysis)
	router.HandleFunc("DELETE /analysis", h.DeleteAnalysis)
}

// GetAnalysis handles patient creation, DICOM storage, and LLM analysis in one request.
//
// @Summary      Create patient and run LLM analysis
// @Description  Creates a new patient with metadata and DICOM files, then triggers LLM analysis. Returns patient data + analysis result.
// @Tags         analysis
// @Accept       mpfd
// @Produce      json
// @Param        formData    formData string true  "Patient metadata as JSON string"
// @Param        dicom_files formData file  true "DICOM image files (multiple allowed)"
// @Success      202 {object} map[string]any
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
	fileHeaders := r.MultipartForm.File["dicom_files"]
	for _, fh := range fileHeaders {
		f, err := fh.Open()
		if err != nil {
			http.Error(w, "Failed to read uploaded file", http.StatusInternalServerError)
			return
		}
		defer f.Close()
		files = append(files, patient.FileInput{Reader: f, Name: fh.Filename})
	}

	patient, err := h.patientService.CreatePatient(&p, files)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	analysisResp, err := h.analysisService.GetAnalysis(patient.ID, patient)
	if err != nil {
		w.WriteHeader(http.StatusAccepted)
		json.NewEncoder(w).Encode(map[string]any{
			"status":  "partial",
			"patient": patient,
			"analysis": map[string]any{
				"error": "Analysis failed: " + err.Error(),
			},
		})
		return
	}

	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]any{
		"status":   "success",
		"patient":  patient,
		"analysis": analysisResp,
	})
}

// DeleteAnalysis removes all patient data, analyses, and DICOM files from the database and disk.
//
// @Summary      Delete all analysis data
// @Description  Deletes all patients, analyses, and DICOM files. Used when starting a new analysis.
// @Tags         analysis
// @Produce      json
// @Success      200 {object} map[string]string
// @Router       /analysis [delete]
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
