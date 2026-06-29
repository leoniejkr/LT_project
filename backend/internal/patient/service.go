package patient

import (
	"backend/internal/analysis"
	"backend/internal/dicom"
	"io"
)

type Service struct {
	repo       *Repository
	dicomStore *dicom.Store
	llmClient  *analysis.LLMClient
}

func NewService(repo *Repository, dicomStore *dicom.Store) *Service {
	return &Service{
		repo:       repo,
		dicomStore: dicomStore,
		llmClient:  analysis.NewLLMClient(),
	}
}

// erstellt patienten und gibt patrientendaten zurück
func (s *Service) CreatePatient(p *Patient, dicomFile io.Reader, filename string) (*Patient, error) {
	if err := s.repo.Create(p); err != nil {
		return nil, err
	}

	path, err := s.dicomStore.Save(p.ID, filename, dicomFile)
	if err != nil {
		return nil, err
	}

	// 3. Pfad im Patienten-Objekt aktualisieren
	p.DicomPath = path
	if err := s.repo.Update(p); err != nil {
		return nil, err
	}
	return p, nil
}

func (s *Service) GetPatient(id uint) (*Patient, error) {
	return s.repo.FindByID(id)
}

func (s *Service) getAnalysis(p *Patient) (*analysis.PredictionResponse, error) {
	return s.llmClient.GetPrediction(p.ID)
}
