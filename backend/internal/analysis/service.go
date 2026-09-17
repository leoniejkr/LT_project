package analysis

import (
	"backend/internal/orthanc"
	"encoding/base64"
	"fmt"
	"log"
)

type Service struct {
	repo         *Repository
	llmClient    *LLMClient
	orthancStore *orthanc.Repository
}

func NewService(repo *Repository, llmClient *LLMClient, orthancStore *orthanc.Repository) *Service {
	return &Service{
		repo:         repo,
		llmClient:    llmClient,
		orthancStore: orthancStore,
	}
}

func (s *Service) GetAnalysis(patientID uint, patientData any, imageBuffers [][]byte, imageNames []string, classifierModel, llmModel string) (*PredictionResponse, error) {
	resp, err := s.llmClient.GetPrediction(patientData, imageBuffers, imageNames, classifierModel, llmModel)
	if err != nil {
		return nil, err
	}

	s.storeHeatmaps(patientID, resp)

	if err := s.persistAnalysis(patientID, resp); err != nil {
		log.Printf("WARNING: Analysis succeeded but persistence failed: %v", err)
	}

	return resp, nil
}

func (s *Service) storeHeatmaps(patientID uint, resp *PredictionResponse) {
	patientName := fmt.Sprintf("Patient_%d", patientID)
	patientIDStr := fmt.Sprintf("%d", patientID)

	for i := range resp.ImageResults {
		for j := range resp.ImageResults[i].Predictions {
			pred := &resp.ImageResults[i].Predictions[j]
			if pred.Heatmap == "" {
				continue
			}

			data, err := base64.StdEncoding.DecodeString(pred.Heatmap)
			if err != nil {
				log.Printf("WARNING: failed to decode heatmap for %s: %v", pred.Class, err)
				continue
			}

			instanceID, err := s.orthancStore.StoreHeatmap(patientName, patientIDStr, data)
			if err != nil {
				log.Printf("WARNING: failed to store heatmap for %s in orthanc: %v", pred.Class, err)
				continue
			}
			pred.OrthancID = instanceID
		}
	}
}

func (s *Service) persistAnalysis(patientID uint, resp *PredictionResponse) error {
	var prediction string
	var confidence float64
	var confidenceReason string

	if len(resp.Predictions) > 0 {
		prediction = resp.Predictions[0].Class
		confidence = resp.Predictions[0].Confidence
		confidenceReason = resp.Predictions[0].Reason
	}

	a := &Analysis{
		PatientID:        patientID,
		Prediction:       prediction,
		Confidence:       confidence,
		ConfidenceReason: confidenceReason,
		Status:           resp.Status,
		ModelVersion:     resp.ModelVersion,
		Predictions:      resp.Predictions,
		ImageResults:     withoutHeatmaps(resp.ImageResults),
	}
	return s.repo.Create(a)
}

// withoutHeatmaps returns a deep copy of the image results where the base64
// heatmap payload is removed for every prediction that was stored in Orthanc.
// Predictions without an Orthanc reference keep their base64 payload as a
// fallback.
func withoutHeatmaps(results ImageResults) ImageResults {
	out := make(ImageResults, len(results))
	for i, img := range results {
		preds := make(ImagePredictions, len(img.Predictions))
		for j, p := range img.Predictions {
			cp := p
			if cp.OrthancID != "" {
				cp.Heatmap = ""
			}
			preds[j] = cp
		}
		out[i] = ImageResult{
			Index:       img.Index,
			Filename:    img.Filename,
			Predictions: preds,
		}
	}
	return out
}

func (s *Service) DeletePatientAnalysis(patientID uint) error {
	return s.repo.DeletePatientAnalysis(patientID)
}

func (s *Service) GetPatientAnalysis(patientID uint) (*Analysis, error) {
	return s.repo.FindByPatientID(patientID)
}

func (s *Service) HasHeatmap(patientID uint, orthancID string) (bool, error) {
	a, err := s.repo.FindByPatientID(patientID)
	if err != nil {
		return false, err
	}
	for _, image := range a.ImageResults {
		for _, prediction := range image.Predictions {
			if prediction.OrthancID == orthancID {
				return true, nil
			}
		}
	}
	return false, nil
}

func (s *Service) GetHeatmapPreview(orthancID string) ([]byte, string, error) {
	return s.orthancStore.GetPreview(orthancID)
}
