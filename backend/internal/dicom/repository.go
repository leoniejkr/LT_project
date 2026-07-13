package dicom

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

type Repository struct {
	baseURL    string
	httpClient *http.Client
}

func NewRepository(baseURL string) *Repository {
	return &Repository{
		baseURL:    strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{},
	}
}

func (s *Repository) Save(patientID uint, filename string, r io.Reader) (string, error) {
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

func (s *Repository) SaveAll(patientID uint, files map[string]io.Reader) ([]string, error) {
	var ids []string
	for filename, r := range files {
		id, err := s.Save(patientID, filename, r)
		if err != nil {
			return nil, fmt.Errorf("failed to save %s: %w", filename, err)
		}
		ids = append(ids, id)
	}
	return ids, nil
}

func (s *Repository) DeleteDicom() error {
	// Orthanc API Endpunkt
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
