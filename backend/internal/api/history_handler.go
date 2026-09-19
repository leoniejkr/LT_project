package api

import (
	"encoding/json"
	"net/http"
	"strconv"
)

// ListPatients godoc
// @Summary      List completed analyses
// @Description  Returns the patients with a persisted, completed analysis, newest first.
// @Tags         history
// @Produce      json
// @Success      200  {array}   PatientSummary  "Completed analysis history"
// @Failure      500  {object}  string          "Unable to load history"
// @Router       /patients [get]
func (h *Handler) ListPatients(w http.ResponseWriter, r *http.Request) {
	patients, err := h.patientService.GetPatients()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	result := make([]PatientSummary, 0, len(patients))
	for _, p := range patients {
		if _, err := h.analysisService.GetPatientAnalysis(p.ID); err == nil {
			result = append(result, PatientSummary{ID: p.ID, Age: p.Age, Gender: string(p.Gender)})
		}
	}
	json.NewEncoder(w).Encode(result)
}

// GetPatientAnalysis godoc
// @Summary      Get a saved analysis
// @Description  Returns a patient and their persisted analysis for the history dashboard.
// @Tags         history
// @Produce      json
// @Param        id   path      int  true  "Patient ID"
// @Success      200  {object}  PatientAnalysisResponse  "Saved analysis"
// @Failure      400  {object}  string                   "Invalid patient ID"
// @Failure      404  {object}  string                   "Patient or analysis not found"
// @Router       /patients/{id}/analysis [get]
func (h *Handler) GetPatientAnalysis(w http.ResponseWriter, r *http.Request) {
	patientID, err := strconv.ParseUint(r.PathValue("id"), 10, 64)
	if err != nil || patientID == 0 {
		http.Error(w, "Invalid patient ID", http.StatusBadRequest)
		return
	}
	p, err := h.patientService.GetPatient(uint(patientID))
	if err != nil {
		http.Error(w, "Patient not found", http.StatusNotFound)
		return
	}
	a, err := h.analysisService.GetPatientAnalysis(p.ID)
	if err != nil {
		http.Error(w, "Analysis not found", http.StatusNotFound)
		return
	}
	json.NewEncoder(w).Encode(PatientAnalysisResponse{
		Status: "success", Patient: newPatientResponse(p), Analysis: newAnalysisResponseFromStored(a),
	})
}

// GetPatientImage godoc
// @Summary      Get a saved patient image
// @Description  Proxies an original X-Ray or Grad-CAM heatmap from Orthanc after verifying it belongs to the patient.
// @Tags         history
// @Produce      image/png
// @Param        id       path  int     true  "Patient ID"
// @Param        imageID  path  string  true  "Orthanc instance ID"
// @Success      200  {file}    file    "Original X-Ray or Grad-CAM heatmap"
// @Failure      400  {object}  string  "Invalid patient or image ID"
// @Failure      404  {object}  string  "Patient or image not found"
// @Failure      502  {object}  string  "Unable to retrieve image from Orthanc"
// @Router       /patients/{id}/images/{imageID} [get]
func (h *Handler) GetPatientImage(w http.ResponseWriter, r *http.Request) {
	patientID, err := strconv.ParseUint(r.PathValue("id"), 10, 64)
	if err != nil || patientID == 0 {
		http.Error(w, "Invalid patient ID", http.StatusBadRequest)
		return
	}
	imageID := r.PathValue("imageID")
	if imageID == "" {
		http.Error(w, "Missing image ID", http.StatusBadRequest)
		return
	}

	isOriginal, err := h.patientService.HasImage(uint(patientID), imageID)
	if err != nil {
		http.Error(w, "Patient not found", http.StatusNotFound)
		return
	}
	isHeatmap := false
	if !isOriginal {
		isHeatmap, _ = h.analysisService.HasHeatmap(uint(patientID), imageID)
	}
	if !isOriginal && !isHeatmap {
		http.Error(w, "Image not found", http.StatusNotFound)
		return
	}
	var image []byte
	var contentType string
	if isOriginal {
		image, contentType, err = h.patientService.GetImagePreview(imageID)
	} else {
		image, contentType, err = h.analysisService.GetHeatmapPreview(imageID)
	}
	if err != nil {
		http.Error(w, "Unable to retrieve image", http.StatusBadGateway)
		return
	}
	if contentType == "" {
		contentType = "image/png"
	}
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Cache-Control", "private, max-age=3600")
	w.Write(image)
}
