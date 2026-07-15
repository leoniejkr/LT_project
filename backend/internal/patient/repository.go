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

func (r *Repository) FindByID(id uint) (*Patient, error) {
	var p Patient
	if err := r.db.First(&p, id).Error; err != nil {
		return nil, err
	}
	return &p, nil
}

func (r *Repository) Update(p *Patient) error {
	return r.db.Save(p).Error
}

func (r *Repository) DeletePatient(patientID uint) error {
	if patientID == 0 {
		return r.db.Where("1 = 1").Delete(&Patient{}).Error
	}
	return r.db.Where("id = ?", patientID).Delete(&Patient{}).Error
}

func (r *Repository) DeleteAll() error {
	return r.db.Where("1 = 1").Delete(&Patient{}).Error
}
