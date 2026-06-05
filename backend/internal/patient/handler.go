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

func (h *Handler) CreatePatient(w http.ResponseWriter, r *http.Request) {
	// TODO
}
