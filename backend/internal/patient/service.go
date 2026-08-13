package patient

import (
	"backend/internal/analysis"
	"backend/internal/orthanc"
	"fmt"
)

type FileInput struct {
	Name  string
	Bytes []byte
}

type Service struct {
	repo            *Repository
	analysisService *analysis.Service
	orthancStore    *orthanc.Repository
}

func NewService(repo *Repository, analysisService *analysis.Service, orthancStore *orthanc.Repository) *Service {
	return &Service{
		repo:            repo,
		analysisService: analysisService,
		orthancStore:    orthancStore,
	}
}

func (s *Service) CreatePatient(p *Patient, files []FileInput) (*Patient, error) {
	if err := s.repo.Create(p); err != nil {
		return nil, err
	}

	patientName := fmt.Sprintf("Patient_%d", p.ID)
	patientID := fmt.Sprintf("%d", p.ID)

	var orthancIDs []string
	for _, f := range files {
		instanceID, err := s.orthancStore.StoreXRays(patientName, patientID, f.Bytes)
		if err != nil {
			return nil, fmt.Errorf("failed to store in orthanc: %w", err)
		}
		orthancIDs = append(orthancIDs, instanceID)
	}

	if len(orthancIDs) > 0 {
		p.OrthancIDs = orthancIDs
		if err := s.repo.Update(p); err != nil {
			return nil, err
		}
	}

	return p, nil
}

func (s *Service) GetAnalysis(patientID uint, patientData *Patient, imageBuffers [][]byte, imageNames []string) (*analysis.PredictionResponse, error) {
	return s.analysisService.GetAnalysis(patientID, patientData, imageBuffers, imageNames)
}

func (s *Service) GetPatient(id uint) (*Patient, error) {
	return s.repo.FindByID(id)
}

func (s *Service) DeleteAllData() error {
	if err := s.analysisService.DeletePatientAnalysis(0); err != nil {
		return err
	}
	return s.repo.DeleteAll()
}
