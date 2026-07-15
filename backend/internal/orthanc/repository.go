package orthanc

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type Repository struct {
	baseURL    string
	httpClient *http.Client
	username   string
	password   string
}

func NewRepository(baseURL, username, password string) *Repository {
	return &Repository{
		baseURL:    baseURL,
		httpClient: &http.Client{},
		username:   username,
		password:   password,
	}
}

func (r *Repository) StoreXRays(patientName, patientID string, pngBytes []byte) (string, error) {
	encoded := base64.StdEncoding.EncodeToString(pngBytes)

	body := map[string]any{
		"Content": "data:image/png;base64," + encoded,
		"Tags": map[string]string{
			"PatientName":       patientName,
			"PatientID":         patientID,
			"StudyDescription":  "Uploaded XRays",
			"Modality":          "XC",
		},
	}

	jsonBody, err := json.Marshal(body)
	if err != nil {
		return "", fmt.Errorf("failed to marshal orthanc request: %w", err)
	}

	req, err := http.NewRequest("POST", r.baseURL+"/tools/create-dicom", bytes.NewReader(jsonBody))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	if r.username != "" && r.password != "" {
		req.SetBasicAuth(r.username, r.password)
	}

	resp, err := r.httpClient.Do(req)
	if err != nil {
		return "", fmt.Errorf("failed to send to orthanc: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read orthanc response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("orthanc returned status %d: %s", resp.StatusCode, string(respBody))
	}

	var result struct {
		ID string `json:"ID"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return "", fmt.Errorf("failed to parse orthanc response: %w", err)
	}

	return result.ID, nil
}
