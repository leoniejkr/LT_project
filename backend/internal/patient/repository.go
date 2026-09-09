package patient

import (
	"fmt"

	"gorm.io/gorm"
)

type Repository struct {
	db *gorm.DB
}

func NewRepository(db *gorm.DB) *Repository {
	return &Repository{db: db}
}

func (r *Repository) Create(p *Patient) error {
	if err := r.db.Create(p).Error; err != nil {
		return fmt.Errorf("failed to create patient: %w", err)
	}
	return nil
}

func (r *Repository) FindByID(patientID uint) (*Patient, error) {
	var p Patient
	if err := r.db.First(&p, patientID).Error; err != nil {
		return nil, err
	}
	return &p, nil
}

func (r *Repository) Update(p *Patient) error {
	return r.db.Save(p).Error
}

func (r *Repository) DeletePatient(patientID uint) error {
	return r.db.Where("id = ?", patientID).Delete(&Patient{}).Error
}

func (r *Repository) DeleteAll() error {
	return r.db.Session(&gorm.Session{AllowGlobalUpdate: true}).Delete(&Patient{}).Error
}
