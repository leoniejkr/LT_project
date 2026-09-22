package api

import (
	"archive/zip"
	"fmt"
	"net/http"
	"strconv"
	"strings"
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

	reports := make([]struct {
		id     uint
		report []byte
	}, 0, len(patients))
	for _, p := range patients {
		report, err := h.buildSessionReport(p.ID)
		if err != nil {
			continue
		}
		reports = append(reports, struct {
			id     uint
			report []byte
		}{id: p.ID, report: report})
	}

	if len(reports) == 0 {
		http.Error(w, "No completed analyses to export.", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/zip")
	w.Header().Set("Content-Disposition", `attachment; filename="history-export.zip"`)

	zw := zip.NewWriter(w)
	defer zw.Close()
	for _, entry := range reports {
		writer, err := zw.Create(fmt.Sprintf("patient-%d.pdf", entry.id))
		if err != nil {
			continue
		}
		if _, err := writer.Write(entry.report); err != nil {
			continue
		}
	}
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

	return buildSessionPDF(p, a, resolve)
}
