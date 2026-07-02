package patient

import "gorm.io/gorm"

type Repository struct {
	db *gorm.DB
}

func NewRepository(db *gorm.DB) *Repository {
	return &Repository{db: db}
}

func (r *Repository) Create(p *Patient) error {
	return r.db.Create(p).Error
}

func (r *Repository) FindByID(id uint) (*Patient, error) {
	var p Patient
	err := r.db.First(&p, id).Error
	return &p, err
}

func (r *Repository) Update(p *Patient) error {
	return r.db.Save(p).Error
}
