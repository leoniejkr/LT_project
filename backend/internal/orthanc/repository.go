package orthanc

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"image"
	"image/draw"
	_ "image/gif"
	_ "image/jpeg"
	"image/png"

	httpclient "backend/internal/http"
)

type Repository struct {
	client *httpclient.Client
}

func NewRepository(baseURL, username, password string) *Repository {
	return &Repository{
		client: httpclient.New(baseURL, httpclient.WithBasicAuth(username, password)),
	}
}

// normalizeImage decodes any supported image format and re-encodes it as a
// standard PNG. Palette-based PNGs are flattened to RGBA because Orthanc's
// built-in PNG reader cannot parse them (PngReader.cpp NotImplemented).
func normalizeImage(data []byte) ([]byte, error) {
	img, _, err := image.Decode(bytes.NewReader(data))
	if err != nil {
		return nil, fmt.Errorf("unsupported image data: %w", err)
	}
	if p, ok := img.(*image.Paletted); ok {
		b := p.Bounds()
		flat := image.NewNRGBA(image.Rect(0, 0, b.Dx(), b.Dy()))
		draw.Draw(flat, flat.Bounds(), p, b.Min, draw.Src)
		img = flat
	}
	var out bytes.Buffer
	if err := png.Encode(&out, img); err != nil {
		return nil, fmt.Errorf("failed to encode image as png: %w", err)
	}
	return out.Bytes(), nil
}

func (r *Repository) StoreXRays(patientName, patientID string, pngBytes []byte) (string, error) {
	pngBytes, err := normalizeImage(pngBytes)
	if err != nil {
		return "", fmt.Errorf("failed to process uploaded image: %w", err)
	}

	encoded := base64.StdEncoding.EncodeToString(pngBytes)

	body := map[string]any{
		"Content": "data:image/png;base64," + encoded,
		"Tags": map[string]string{
			"PatientName":      patientName,
			"PatientID":        patientID,
			"StudyDescription": "Uploaded XRays",
			"Modality":         "XC",
		},
	}

	var result struct {
		ID string `json:"ID"`
	}
	if err := r.client.PostJSON("/tools/create-dicom", body, &result); err != nil {
		return "", fmt.Errorf("failed to send to orthanc: %w", err)
	}

	return result.ID, nil
}