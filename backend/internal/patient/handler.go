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

	// TODO: wie kriege ich es hin single-responsibility mäßig hier
	// bei create patient wirklich nur das anlegen
	// des patienten zu machen, aber gleichzeitig zu ermöglichen, dass
	// analyseergebnisse "automatisch" zurückgegeben werden, wenn
	// ein patient angelegt wird?

	err := r.ParseMultipartForm(10 << 20)
	if err != nil {
		http.Error(w, "Unable to parse multipart form", http.StatusBadRequest)
		return
	}

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

	file, header, err := r.FormFile("dicom_file")
	if err != nil {
		http.Error(w, "Missing dicom_file", http.StatusBadRequest)
		return
	}
	defer file.Close()

	patient, err := h.service.CreatePatient(&p, file, header.Filename)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusAccepted)
	json.NewEncoder(w).Encode(map[string]any{
		"status":              "success",
		"id":                  patient.ID,
		"age":                 patient.Age,
		"gender":              patient.Gender,
		"admitted_to_icu":     patient.AdmittedToIcu,
		"requires_ventilator": patient.RequiresVentilator,
		"known_illnesses":     patient.KnownIllnesses,
		"symptoms":            patient.Symptoms,
		"dicom_path":          patient.DicomPath,
	})
}
