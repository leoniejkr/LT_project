package analysis

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

func (s *Service) GetAnalysis(patientID uint, patientData any) (*PredictionResponse, error) {
	resp, err := s.llmClient.GetPrediction(patientData)
	if err != nil {
		return nil, err
	}

	if err := s.persistAnalysis(patientID, resp); err != nil {
		return nil, err
	}

	return resp, nil
}

func (s *Service) persistAnalysis(patientID uint, resp *PredictionResponse) error {
	a := &Analysis{
		PatientID:        patientID,
		Prediction:       resp.Prediction,
		Confidence:       resp.Confidence,
		ConfidenceReason: resp.ConfidenceReason,
		Status:           resp.Status,
	}
	return s.repo.Create(a)
}

func (s *Service) DeletePatientAnalysis(patientID uint) error {
	return s.repo.DeletePatientAnalysis(patientID)
}
