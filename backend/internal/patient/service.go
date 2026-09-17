package patient

import (
	"backend/internal/orthanc"
	"fmt"
)

type Service struct {
	repo         *Repository
	orthancStore *orthanc.Repository
}

func NewService(repo *Repository, orthancStore *orthanc.Repository) *Service {
	return &Service{
		repo:         repo,
		orthancStore: orthancStore,
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

func (s *Service) GetPatient(id uint) (*Patient, error) {
	return s.repo.FindByID(id)
}

func (s *Service) GetPatients() ([]Patient, error) {
	return s.repo.FindAll()
}

func (s *Service) DeletePatient(id uint) error {
	return s.repo.DeletePatient(id)
}

func (s *Service) DeleteAll() error {
	return s.repo.DeleteAll()
}

func (s *Service) HasImage(id uint, orthancID string) (bool, error) {
	p, err := s.repo.FindByID(id)
	if err != nil {
		return false, err
	}
	for _, imageID := range p.OrthancIDs {
		if imageID == orthancID {
			return true, nil
		}
	}
	return false, nil
}

func (s *Service) GetImagePreview(orthancID string) ([]byte, string, error) {
	return s.orthancStore.GetPreview(orthancID)
}
