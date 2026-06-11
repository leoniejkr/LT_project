package patient

import (
	"encoding/json"
	"net/http"
)

type Handler struct {
	service *Service
}

func NewHandler(s *Service) *Handler {
	return &Handler{service: s}
}

func (h *Handler) RegisterRoutes(router *http.ServeMux) {
	router.HandleFunc("POST /patients", h.CreatePatient)
}

// CreatePatient Godoc
// @Summary      Create a new patient
// @Description  Creates new patient with the provided metadata and dicom images
// @Tags         patients
// @Accept       mpfd
// @Produce      json
// @Param        formData    formData string true  "Patienten-Metadata as JSON-String"
// @Param        dicom_file  formData file   true  "The .dcm picture data"
// @Success      202      {string} string "Accepted"
// @Router       /patients [post]
func (h *Handler) CreatePatient(w http.ResponseWriter, r *http.Request) {
	// 1. Multipart Form parsen (max. 10MB im Speicher)
	err := r.ParseMultipartForm(10 << 20)
	if err != nil {
		http.Error(w, "Unable to parse multipart form", http.StatusBadRequest)
		return
	}

	// 2. JSON-Daten aus dem "formData" Feld extrahieren
	formData := r.FormValue("formData")
	if formData == "" {
		http.Error(w, "Missing formData", http.StatusBadRequest)
		return
	}

	var p Patient
	if err := json.Unmarshal([]byte(formData), &p); err != nil {
		http.Error(w, "Invalid JSON in formData", http.StatusBadRequest)
		return
	}

	// 3. DICOM-Datei extrahieren
	file, header, err := r.FormFile("dicom_file")
	if err != nil {
		http.Error(w, "Missing dicom_file", http.StatusBadRequest)
		return
	}
	defer file.Close()

	// 4. Service aufrufen (Metadaten + Datei)
	prediction, err := h.service.CreatePatient(&p, file, header.Filename)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]any{
		"status":            "success",
		"id":                p.ID,
		"prediction":        prediction.Prediction,
		"confidence":        prediction.Confidence,
		"confidence_reason": prediction.Confidence_Reason,
		"model_version":     prediction.ModelVersion,
		"is_mock":           prediction.IsMock,
	})
}
