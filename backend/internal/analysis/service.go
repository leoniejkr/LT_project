package analysis

import "log"

type Service struct {
	repo      *Repository
	llmClient *LLMClient
}

func NewService(repo *Repository, llmClient *LLMClient) *Service {
	return &Service{
		repo:      repo,
		llmClient: llmClient,
	}
}

func (s *Service) GetAnalysis(patientID uint, patientData any, imageBuffers [][]byte, imageNames []string, classifierModel, llmModel string) (*PredictionResponse, error) {
	resp, err := s.llmClient.GetPrediction(patientData, imageBuffers, imageNames, classifierModel, llmModel)
	if err != nil {
		return nil, err
	}

	if err := s.persistAnalysis(patientID, resp); err != nil {
		log.Printf("WARNING: Analysis succeeded but persistence failed: %v", err)
	}

	return resp, nil
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
		ImageResults:     resp.ImageResults,
	}
	return s.repo.Create(a)
}

func (s *Service) DeletePatientAnalysis(patientID uint) error {
	return s.repo.DeletePatientAnalysis(patientID)
}
