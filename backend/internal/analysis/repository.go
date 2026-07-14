package analysis

import "gorm.io/gorm"

type Repository struct {
	db *gorm.DB
}

func NewRepository(db *gorm.DB) *Repository {
	return &Repository{db: db}
}

func (r *Repository) Create(a *Analysis) error {
	return r.db.Create(a).Error
}

func (r *Repository) FindByPatientID(patientID uint) (*Analysis, error) {
	var a Analysis
	err := r.db.Where("patient_id = ?", patientID).First(&a).Error
	return &a, err
}

func (r *Repository) DeletePatientAnalysis(patientID uint) error {
	err := r.db.Where("patient_id = ?", patientID).Delete(&Analysis{}).Error
	if err != nil {
		return fmt.Errorf("failed to delete patient analysis: %w", err)
	}
	return nil
}
