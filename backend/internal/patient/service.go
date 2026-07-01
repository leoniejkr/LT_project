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

	var savedPaths []string
	for _, f := range files {
		path, err := s.dicomStore.Save(p.ID, f.Name, f.Reader)
		if err != nil {
			return nil, err
		}
		savedPaths = append(savedPaths, path)
	}

	if len(savedPaths) > 0 {
		p.DicomPaths = savedPaths
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
