package patient

import (
	"backend/internal/analysis"
	"backend/internal/dicom"
	"io"
)

type FileInput struct {
	Reader io.Reader
	Name   string
}

type CreatePatientResult struct {
	Patient  *Patient
	Analysis *analysis.PredictionResponse
}

type Service struct {
	repo            *Repository
	dicomStore      *dicom.Repository
	analysisService *analysis.Service
}

func NewService(repo *Repository, dicomStore *dicom.Repository, analysisService *analysis.Service) *Service {
	return &Service{
		repo:            repo,
		dicomStore:      dicomStore,
		analysisService: analysisService,
	}
}

func (s *Service) CreatePatient(p *Patient, files []FileInput) (*Patient, error) {
	if err := s.repo.Create(p); err != nil {
		return nil, err
	}

	var orthancIDs []string
	for _, f := range files {
		id, err := s.dicomStore.Save(p.ID, f.Name, f.Reader)
		if err != nil {
			return nil, err
		}
		orthancIDs = append(orthancIDs, id)
	}

	if len(orthancIDs) > 0 {
		p.DicomPaths = orthancIDs
		if err := s.repo.Update(p); err != nil {
			return nil, err
		}
	}

	return p, nil
}

func (s *Service) GetAnalysis(patientID uint, patientData any) (*analysis.PredictionResponse, error) {
	return s.analysisService.GetAnalysis(patientID, patientData)
}

func (s *Service) GetPatient(id uint) (*Patient, error) {
	return s.repo.FindByID(id)
}

func (s *Service) DeleteAllData() error {
	if err := s.analysisService.DeletePatientAnalysis(0); err != nil {
		return err
	}
	if err := s.repo.DeletePatient(0); err != nil {
		return err
	}
	return s.dicomStore.DeleteDicom()
}
