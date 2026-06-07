package patient

import (
	"backend/internal/dicom"
	"io"
)

type Service struct {
	repo       *Repository
	dicomStore *dicom.Store
}

func NewService(repo *Repository, dicomStore *dicom.Store) *Service {
	return &Service{
		repo:       repo,
		dicomStore: dicomStore,
	}
}

func (s *Service) CreatePatient(p *Patient, dicomFile io.Reader, filename string) error {
	// 1. Patienten in DB anlegen (noch ohne Pfad) um ID zu generieren
	if err := s.repo.Create(p); err != nil {
		return err
	}

	// 2. DICOM speichern
	path, err := s.dicomStore.Save(p.ID, filename, dicomFile)
	if err != nil {
		return err
	}

	// 3. Pfad im Patienten-Objekt aktualisieren
	p.DicomPath = path
	return s.repo.Update(p)
}

func (s *Service) GetPatient(id uint) (*Patient, error) {
	return s.repo.FindByID(id)
}
