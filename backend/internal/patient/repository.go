package patient

import (
	"gorm.io/gorm"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

type Repository struct {
	db *gorm.DB
	baseURL    string
	httpClient *http.Client
}

func NewRepository(db *gorm.DB, baseURL string) *Repository {
	return &Repository{
		db:         db,
		baseURL:    baseURL,
		httpClient: &http.Client{},
	}
}

func (r *Repository) Create(p *Patient) error {
	// Save patient to PostgreSQL
	err := r.db.Create(p).Error
	if err != nil {
		return fmt.Errorf("failed to create patient in PostgreSQL: %w", err)
	}

	// Save patient to Orthanc
	body, err := io.ReadAll(r)
	if err != nil {
		return "", fmt.Errorf("failed to read X-Ray data: %w", err)
	}

	req, err := http.NewRequest("POST", s.baseURL+"/instances", strings.NewReader(string(body)))
	if err != nil {
		return "", fmt.Errorf("failed to create Orthanc request: %w", err)
	}
	req.Header.Set("Content-Type", "application/dicom")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to upload to Orthanc: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		respBody, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("Orthanc returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result struct {
		ID string `json:"ID"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("failed to decode Orthanc response: %w", err)
	}

	return result.ID, nil
}

func (r *Repository) FindByID(id uint) (*Patient, error) {
	var p Patient
	err := r.db.First(&p, id).Error
	return &p, err
}

func (r *Repository) Update(p *Patient) error {
	return r.db.Save(p).Error
}

func (r *Repository) DeletePatient(patientID uint) error {
	// Delete patient from PostgreSQL
	err := r.db.Where("id = ?", patientID).Delete(&Patient{}).Error
	if err != nil {
		return fmt.Errorf("failed to delete patient from PostgreSQL: %w", err)
	}

	// Delete patient from Orthanc
	resp, err := s.httpClient.Get(s.baseURL + "/patients")
	if err != nil {
		return fmt.Errorf("failed to list Orthanc patients: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Orthanc returned status %d when listing patients", resp.StatusCode)
	}

	// Es wird immer eine Liste zurückgegeben, aber "per Definition" gibt es nie mehr als einen Eintrag
	var patientIDs []string
	if err := json.NewDecoder(resp.Body).Decode(&patientIDs); err != nil {
		return fmt.Errorf("failed to decode Orthanc patient list: %w", err)
	}

	if len(patientIDs) == 0 {
		return nil
	}

	req, err := http.NewRequest("DELETE", s.baseURL+"/patients/"+patientIDs[0], nil)
	if err != nil {
		return fmt.Errorf("failed to create delete request: %w", err)
	}
	delResp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to delete Orthanc patient %s: %w", patientIDs[0], err)
	}
	delResp.Body.Close()
	if delResp.StatusCode != http.StatusOK {
		return fmt.Errorf("Orthanc returned status %d when deleting patient %s", delResp.StatusCode, patientIDs[0])
	}

	return nil

}
