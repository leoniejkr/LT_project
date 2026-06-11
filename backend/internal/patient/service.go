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

func (s *Service) CreatePatient(p *Patient, dicomFile io.Reader, filename string) (*analysis.PredictionResponse, error) {
	// 1. Patienten in DB anlegen (noch ohne Pfad) um ID zu generieren
	if err := s.repo.Create(p); err != nil {
		return nil, err
	}

	// 2. DICOM speichern
	path, err := s.dicomStore.Save(p.ID, filename, dicomFile)
	if err != nil {
		return nil, err
	}

	// 3. Pfad im Patienten-Objekt aktualisieren
	p.DicomPath = path
	if err := s.repo.Update(p); err != nil {
		return nil, err
	}

	// 4. Analyse aufrufen
	return s.llmClient.GetPrediction()
}

func (s *Service) GetPatient(id uint) (*Patient, error) {
	return s.repo.FindByID(id)
}
