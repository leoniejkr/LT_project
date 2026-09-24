package api

import (
	"archive/zip"
	"backend/internal/export"
	"bytes"
	"errors"
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"gorm.io/gorm"
)

// ExportPatient godoc
// @Summary      Export one session as PDF
// @Description  Generates a PDF report (patient data, findings, original X-ray and heatmaps) for a saved analysis.
// @Tags         history
// @Produce      application/pdf
// @Param        id  path  int  true  "Patient ID"
// @Success      200  {file}  file  "PDF export"
// @Failure      400  {object}  string  "Invalid patient ID"
// @Failure      404  {object}  string  "Patient or analysis not found"
// @Failure      500  {object}  string  "Export generation failed"
// @Router       /patients/{id}/export [get]
func (h *Handler) ExportPatient(w http.ResponseWriter, r *http.Request) {
	patientID, err := strconv.ParseUint(r.PathValue("id"), 10, 64)
	if err != nil || patientID == 0 {
		http.Error(w, "Invalid patient ID", http.StatusBadRequest)
		return
	}
	report, err := h.buildSessionReport(uint(patientID))
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			http.Error(w, err.Error(), http.StatusNotFound)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/pdf")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="analysis-%d.pdf"`, patientID))
	w.Write(report)
}

// ExportAll godoc
// @Summary      Export all sessions as PDFs in a ZIP archive
// @Description  Generates one PDF report per saved analysis and bundles them into a single ZIP download.
// @Tags         history
// @Produce      application/zip
// @Success      200  {file}  file  "ZIP with one PDF per session"
// @Failure      500  {object}  string  "Export generation failed"
// @Router       /export [get]
func (h *Handler) ExportAll(w http.ResponseWriter, r *http.Request) {
	patients, err := h.patientService.GetPatients()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	var archive bytes.Buffer
	zw := zip.NewWriter(&archive)
	exported := 0
	for _, p := range patients {
		// Patients are created before their analysis is complete. Keep those
		// in-progress records out of the history export, just as ListPatients
		// keeps them out of the history page.
		if _, err := h.analysisService.GetPatientAnalysis(p.ID); err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				continue
			}
			http.Error(w, fmt.Sprintf("Failed to load analysis for patient %d: %v", p.ID, err), http.StatusInternalServerError)
			return
		}

		report, err := h.buildSessionReport(p.ID)
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to export patient %d: %v", p.ID, err), http.StatusInternalServerError)
			return
		}
		writer, err := zw.Create(fmt.Sprintf("patient-%d.pdf", p.ID))
		if err != nil {
			http.Error(w, "Failed to create ZIP entry: "+err.Error(), http.StatusInternalServerError)
			return
		}
		if _, err := writer.Write(report); err != nil {
			http.Error(w, "Failed to write ZIP entry: "+err.Error(), http.StatusInternalServerError)
			return
		}
		exported++
	}
	if exported == 0 {
		http.Error(w, "No completed analyses to export.", http.StatusNotFound)
		return
	}
	if err := zw.Close(); err != nil {
		http.Error(w, "Failed to finalize ZIP archive: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/zip")
	w.Header().Set("Content-Disposition", `attachment; filename="history-export.zip"`)
	w.Write(archive.Bytes())
}

func (h *Handler) buildSessionReport(patientID uint) ([]byte, error) {
	p, err := h.patientService.GetPatient(patientID)
	if err != nil {
		return nil, fmt.Errorf("patient not found")
	}
	a, err := h.analysisService.GetPatientAnalysis(patientID)
	if err != nil {
		return nil, fmt.Errorf("analysis not found")
	}

	resolve := func(orthancID string) ([]byte, string, error) {
		isOriginal, err := h.patientService.HasImage(patientID, orthancID)
		if err == nil && isOriginal {
			return h.patientService.GetImagePreview(orthancID)
		}
		isHeatmap, _ := h.analysisService.HasHeatmap(patientID, orthancID)
		if isHeatmap {
			return h.analysisService.GetHeatmapPreview(orthancID)
		}
		return nil, "", fmt.Errorf("image %s not found for patient %d", orthancID, patientID)
	}

	return export.BuildSessionPDF(p, a, resolve)
}
