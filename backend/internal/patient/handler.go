package patient

import "net/http"

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
// @Accept       json
// @Produce      json
// @Param        patient  body      Patient  true  "Patient Data"
// @Success      201      {object}  Patient
// @Router       /patients [post]
func (h *Handler) CreatePatient(w http.ResponseWriter, r *http.Request) {
	// TODO
}
