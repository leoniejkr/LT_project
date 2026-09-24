package export

import (
	"backend/internal/analysis"
	"backend/internal/patient"
	"bytes"
	"fmt"
	"strings"

	"github.com/go-pdf/fpdf"
)

// ImageResolver returns the raw bytes of an Orthanc preview (original or
// heatmap) for embedding in the PDF. Implemented by the export handler so the
// PDF builder stays free of service dependencies.
type ImageResolver func(orthancID string) ([]byte, string, error)

type rgb struct{ r, g, b int }

var pdfHeaderFill = rgb{237, 242, 247}
var pdfAltRowFill = rgb{246, 248, 250}

// BuildSessionPDF renders a patient analysis as a PDF report.
func BuildSessionPDF(p *patient.Patient, a *analysis.Analysis, resolve ImageResolver) ([]byte, error) {
	pdf := fpdf.New("P", "mm", "A4", "")
	pdf.SetTopMargin(15)
	pdf.SetLeftMargin(15)
	pdf.SetRightMargin(15)
	pdf.SetAutoPageBreak(true, 18)
	pdf.AddPage()

	renderSession(pdf, p, a, resolve)

	var buf bytes.Buffer
	if err := pdf.Output(&buf); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

func renderSession(pdf *fpdf.Fpdf, p *patient.Patient, a *analysis.Analysis, resolve ImageResolver) {
	pdf.SetFont("Helvetica", "B", 18)
	pdf.SetTextColor(20, 20, 30)
	pdf.CellFormat(0, 10, "Medical Analysis Report", "", 0, "L", false, 0, "")

	pdf.SetFont("Helvetica", "", 9)
	pdf.SetTextColor(120, 120, 130)
	pdf.CellFormat(0, 6, fmt.Sprintf("Patient #%d", p.ID), "", 1, "R", false, 0, "")
	pdf.Ln(3)

	pdf.SetFont("Helvetica", "B", 11)
	pdf.SetTextColor(20, 20, 30)
	pdf.CellFormat(0, 7, "Patient", "", 1, "L", false, 0, "")
	pdf.SetFont("Helvetica", "", 10)
	pdf.SetTextColor(40, 40, 50)
	pdf.CellFormat(0, 6, fmt.Sprintf("Age: %d years", p.Age), "", 1, "L", false, 0, "")
	pdf.CellFormat(0, 6, fmt.Sprintf("Gender: %s", p.Gender), "", 1, "L", false, 0, "")
	if len(p.Symptoms) > 0 {
		pdf.MultiCell(0, 5, "Symptoms: "+strings.Join(symptomStrings(p.Symptoms), ", "), "", "L", false)
	}
	if len(p.History) > 0 {
		pdf.MultiCell(0, 5, "Medical history: "+strings.Join(historyStrings(p.History), ", "), "", "L", false)
	}
	pdf.Ln(2)
	pdf.SetFont("Helvetica", "", 9)
	pdf.SetTextColor(120, 120, 130)
	if a.ModelVersion != "" {
		pdf.CellFormat(0, 5, "Model: "+a.ModelVersion, "", 1, "L", false, 0, "")
	}
	pdf.CellFormat(0, 5, "Status: "+a.Status, "", 1, "L", false, 0, "")
	pdf.Ln(4)

	pdf.SetFont("Helvetica", "B", 11)
	pdf.SetTextColor(20, 20, 30)
	pdf.CellFormat(0, 7, "Findings", "", 1, "L", false, 0, "")

	if len(a.Predictions) == 0 {
		pdf.SetFont("Helvetica", "I", 10)
		pdf.SetTextColor(40, 40, 50)
		pdf.CellFormat(0, 6, "No findings reported.", "", 1, "L", false, 0, "")
		pdf.Ln(3)
	} else {
		renderFindingsTable(pdf, a.Predictions)
		pdf.Ln(4)
	}

	for i, img := range a.ImageResults {
		renderImageSection(pdf, i, img, p, resolve)
	}
}

func renderFindingsTable(pdf *fpdf.Fpdf, predictions analysis.Predictions) {
	widths := []float64{45, 25, 120}
	xStart, xConf, xReason := 15.0, 15.0+45, 15.0+45+25

	pdf.SetFont("Helvetica", "B", 9)
	pdf.SetFillColor(pdfHeaderFill.r, pdfHeaderFill.g, pdfHeaderFill.b)
	pdf.CellFormat(widths[0], 6, "Finding", "1", 0, "L", true, 0, "")
	pdf.CellFormat(widths[1], 6, "Confidence", "1", 0, "L", true, 0, "")
	pdf.CellFormat(widths[2], 6, "Rationale", "1", 1, "L", true, 0, "")

	pdf.SetFont("Helvetica", "", 9)
	for row, pred := range predictions {
		if row%2 == 0 {
			pdf.SetFillColor(255, 255, 255)
		} else {
			pdf.SetFillColor(pdfAltRowFill.r, pdfAltRowFill.g, pdfAltRowFill.b)
		}
		y := pdf.GetY()
		classLines := pdf.SplitLines([]byte(pred.Class), widths[0])
		reasonLines := pdf.SplitLines([]byte(pred.Reason), widths[2])
		rows := len(classLines)
		if len(reasonLines) > rows {
			rows = len(reasonLines)
		}
		if rows < 1 {
			rows = 1
		}
		rowHeight := float64(rows) * 5

		pdf.SetXY(xStart, y)
		pdf.MultiCell(widths[0], 5, pred.Class, "LBT", "L", true)
		pdf.SetXY(xConf, y)
		pdf.MultiCell(widths[1], 5, fmt.Sprintf("%.1f%%", pred.Confidence*100), "LBT", "L", true)
		pdf.SetXY(xReason, y)
		pdf.MultiCell(widths[2], 5, pred.Reason, "LBR", "L", true)
		pdf.SetY(y + rowHeight)
	}
}

func renderImageSection(pdf *fpdf.Fpdf, index int, img analysis.ImageResult, p *patient.Patient, resolve ImageResolver) {
	pdf.SetFont("Helvetica", "B", 12)
	pdf.SetTextColor(20, 20, 30)
	pdf.CellFormat(0, 7, fmt.Sprintf("Image %d: %s", index+1, img.Filename), "", 1, "L", false, 0, "")
	pdf.Ln(2)

	originalID := ""
	if index < len(p.OrthancIDs) {
		originalID = p.OrthancIDs[index]
	}
	if originalID != "" {
		embedImage(pdf, resolve, originalID, 95, "Original X-Ray")
	} else {
		pdf.SetFont("Helvetica", "I", 9)
		pdf.SetTextColor(150, 150, 160)
		pdf.CellFormat(0, 5, "Original image unavailable.", "", 1, "L", false, 0, "")
	}

	pdf.Ln(3)
	if len(img.Predictions) == 0 {
		pdf.SetFont("Helvetica", "I", 9)
		pdf.SetTextColor(120, 120, 130)
		pdf.CellFormat(0, 5, "No class activation images for this scan.", "", 1, "L", false, 0, "")
		return
	}

	pdf.SetFont("Helvetica", "B", 10)
	pdf.SetTextColor(20, 20, 30)
	pdf.CellFormat(0, 6, "Localized Findings (Grad-CAM)", "", 1, "L", false, 0, "")
	for _, pred := range img.Predictions {
		if pred.OrthancID == "" {
			continue
		}
		embedImage(pdf, resolve, pred.OrthancID, 52, fmt.Sprintf("%s (%.1f%%)", pred.Class, pred.Confidence*100))
	}
	pdf.Ln(4)
}

func embedImage(pdf *fpdf.Fpdf, resolve ImageResolver, orthancID string, width float64, centeredLabel string) {
	data, contentType, err := resolve(orthancID)
	if err != nil || len(data) == 0 {
		pdf.SetFont("Helvetica", "I", 9)
		pdf.SetTextColor(150, 150, 160)
		pdf.CellFormat(0, 5, "Image unavailable.", "", 1, "L", false, 0, "")
		return
	}
	imageType := detectImageType(data, contentType)

	options := fpdf.ImageOptions{ImageType: imageType, ReadDpi: true}
	info := pdf.RegisterImageOptionsReader("img_"+orthancID, options, bytes.NewReader(data))
	wd, ht := info.Extent()
	if wd <= 0 || ht <= 0 {
		pdf.SetFont("Helvetica", "I", 9)
		pdf.SetTextColor(150, 150, 160)
		pdf.CellFormat(0, 5, "Image could not be parsed.", "", 1, "L", false, 0, "")
		return
	}

	height := width * ht / wd
	pageWidth, pageHeight := pdf.GetPageSize()
	maxWidth := pageWidth - 30
	if width > maxWidth {
		width = maxWidth
		height = width * ht / wd
	}

	if pdf.GetY()+height > pageHeight-18 {
		pdf.AddPage()
	}
	x := (pageWidth - width) / 2
	y := pdf.GetY()
	pdf.Image("img_"+orthancID, x, y, width, height, false, imageType, 0, "")

	if centeredLabel != "" {
		pdf.SetFont("Helvetica", "B", 8)
		pdf.SetTextColor(60, 60, 70)
		labelWidth := pdf.GetStringWidth(centeredLabel) + 4
		pdf.SetXY((pageWidth-labelWidth)/2, y+height+1)
		pdf.CellFormat(labelWidth, 4, centeredLabel, "0", 0, "C", false, 0, "")
	}
	pdf.SetY(y + height + 6)
}

func detectImageType(data []byte, contentType string) string {
	switch {
	case bytes.HasPrefix(data, []byte("\x89PNG")):
		return "PNG"
	case bytes.HasPrefix(data, []byte("\xff\xd8")):
		return "JPG"
	case bytes.HasPrefix(data, []byte("GIF")):
		return "GIF"
	}
	if strings.Contains(strings.ToLower(contentType), "png") {
		return "PNG"
	}
	if strings.Contains(strings.ToLower(contentType), "jpeg") || strings.Contains(strings.ToLower(contentType), "jpg") {
		return "JPG"
	}
	return "PNG"
}

func symptomStrings(s patient.Symptoms) []string {
	out := make([]string, len(s))
	for i, symptom := range s {
		out[i] = string(symptom)
	}
	return out
}

func historyStrings(h patient.Histories) []string {
	out := make([]string, len(h))
	for i, entry := range h {
		out[i] = string(entry)
	}
	return out
}
