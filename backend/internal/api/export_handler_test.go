package api

import (
	"archive/zip"
	"bytes"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"backend/internal/patient"
)

func TestExportAll_ReturnsCompleteZIP(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	p, err := handler.patientService.CreatePatient(&patient.Patient{Age: 42, Gender: patient.GenderMale}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := handler.analysisService.GetAnalysis(p.ID, p, nil, nil, "", ""); err != nil {
		t.Fatal(err)
	}

	w := httptest.NewRecorder()
	handler.ExportAll(w, httptest.NewRequest(http.MethodGet, "/export", nil))
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", w.Code, http.StatusOK, w.Body.String())
	}
	if got := w.Header().Get("Content-Type"); got != "application/zip" {
		t.Fatalf("content type = %q, want application/zip", got)
	}
	archive, err := zip.NewReader(bytes.NewReader(w.Body.Bytes()), int64(w.Body.Len()))
	if err != nil {
		t.Fatalf("invalid ZIP: %v", err)
	}
	if len(archive.File) != 1 || archive.File[0].Name != "patient-1.pdf" {
		t.Fatalf("ZIP entries = %v, want patient-1.pdf", archive.File)
	}
	file, err := archive.File[0].Open()
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()
	header := make([]byte, 4)
	if _, err := file.Read(header); err != nil {
		t.Fatal(err)
	}
	if string(header) != "%PDF" {
		t.Errorf("report header = %q, want %%PDF", header)
	}
}

func TestExportAll_SkipsPatientsWithoutCompletedAnalysis(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	missing, err := handler.patientService.CreatePatient(&patient.Patient{Age: 42, Gender: patient.GenderMale}, nil)
	if err != nil {
		t.Fatal(err)
	}
	complete, err := handler.patientService.CreatePatient(&patient.Patient{Age: 43, Gender: patient.GenderFemale}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := handler.analysisService.GetAnalysis(complete.ID, complete, nil, nil, "", ""); err != nil {
		t.Fatal(err)
	}

	w := httptest.NewRecorder()
	handler.ExportAll(w, httptest.NewRequest(http.MethodGet, "/export", nil))
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d: %s", w.Code, http.StatusOK, w.Body.String())
	}
	archive, err := zip.NewReader(bytes.NewReader(w.Body.Bytes()), int64(w.Body.Len()))
	if err != nil {
		t.Fatalf("invalid ZIP: %v", err)
	}
	if len(archive.File) != 1 || archive.File[0].Name != fmt.Sprintf("patient-%d.pdf", complete.ID) {
		t.Fatalf("ZIP entries = %v, want only patient-%d.pdf (patient %d is incomplete)", archive.File, complete.ID, missing.ID)
	}
}

func TestExportAll_ReturnsNotFoundWhenNoAnalysisIsComplete(t *testing.T) {
	handler, llmSrv, orthancSrv := setupHandler(t, defaultLLMHandler())
	defer llmSrv.Close()
	defer orthancSrv.Close()

	if _, err := handler.patientService.CreatePatient(&patient.Patient{Age: 42, Gender: patient.GenderMale}, nil); err != nil {
		t.Fatal(err)
	}

	w := httptest.NewRecorder()
	handler.ExportAll(w, httptest.NewRequest(http.MethodGet, "/export", nil))
	if w.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want %d: %s", w.Code, http.StatusNotFound, w.Body.String())
	}
	if !strings.Contains(w.Body.String(), "No completed analyses") {
		t.Errorf("body = %q, want no completed analyses message", w.Body.String())
	}
}
