package patient

import (
	"testing"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupPatientDB(t *testing.T) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open test db: %v", err)
	}
	if err := db.AutoMigrate(&Patient{}); err != nil {
		t.Fatalf("failed to migrate: %v", err)
	}
	return db
}

func TestCreate_Success(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)

	p := &Patient{
		Age:      62,
		Gender:   GenderMale,
		History:  Histories{History("Asthma, COPD, or Emphysema")},
		Symptoms: Symptoms{SymptomProductiveCough, SymptomFever},
	}

	if err := repo.Create(p); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if p.ID == 0 {
		t.Error("expected ID to be set after create")
	}
}

func TestFindByID_Found(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)

	created := &Patient{
		Age:      45,
		Gender:   GenderFemale,
		History:  Histories{History("Known pleural effusion")},
		Symptoms: Symptoms{SymptomFatigue},
	}
	repo.Create(created)

	found, err := repo.FindByID(created.ID)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if found.Age != 45 {
		t.Errorf("age = %d, want 45", found.Age)
	}
	if found.Gender != GenderFemale {
		t.Errorf("gender = %q, want %q", found.Gender, GenderFemale)
	}
}

func TestFindByID_NotFound(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)

	_, err := repo.FindByID(999)
	if err == nil {
		t.Fatal("expected error for non-existent patient")
	}
}

func TestFindAll_NewestFirst(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)
	repo.Create(&Patient{Age: 20, Gender: GenderMale})
	repo.Create(&Patient{Age: 30, Gender: GenderFemale})

	patients, err := repo.FindAll()
	if err != nil {
		t.Fatalf("FindAll returned error: %v", err)
	}
	if len(patients) != 2 {
		t.Fatalf("got %d patients, want 2", len(patients))
	}
	if patients[0].Age != 30 || patients[1].Age != 20 {
		t.Errorf("patients are not ordered newest first: %#v", patients)
	}
}

func TestUpdate(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)

	p := &Patient{Age: 30, Gender: GenderMale}
	repo.Create(p)

	p.History = Histories{History("Recent surgery (anesthesia / open-heart)")}
	p.OrthancIDs = ImagePaths{"id-1", "id-2"}
	if err := repo.Update(p); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	found, _ := repo.FindByID(p.ID)
	if len(found.History) != 1 {
		t.Errorf("history len = %d, want 1", len(found.History))
	}
	if len(found.OrthancIDs) != 2 {
		t.Errorf("orthanc ids len = %d, want 2", len(found.OrthancIDs))
	}
}

func TestDeletePatient_BySpecificID(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)

	p1 := &Patient{Age: 20, Gender: GenderMale}
	p2 := &Patient{Age: 30, Gender: GenderFemale}
	repo.Create(p1)
	repo.Create(p2)

	if err := repo.DeletePatient(p1.ID); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	_, err := repo.FindByID(p1.ID)
	if err == nil {
		t.Fatal("expected patient 1 to be deleted")
	}

	found, err := repo.FindByID(p2.ID)
	if err != nil {
		t.Fatalf("patient 2 should still exist: %v", err)
	}
	if found.Age != 30 {
		t.Errorf("patient 2 age = %d, want 30", found.Age)
	}
}

func TestDeleteAll(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)

	repo.Create(&Patient{Age: 20, Gender: GenderMale})
	repo.Create(&Patient{Age: 30, Gender: GenderFemale})
	repo.Create(&Patient{Age: 40, Gender: GenderDiverse})

	if err := repo.DeleteAll(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	var count int64
	db.Model(&Patient{}).Count(&count)
	if count != 0 {
		t.Errorf("expected 0 patients after delete all, got %d", count)
	}
}

func TestCreate_AllGenders(t *testing.T) {
	db := setupPatientDB(t)
	repo := NewRepository(db)

	genders := []Gender{GenderMale, GenderFemale, GenderDiverse}
	for _, g := range genders {
		p := &Patient{Age: 25, Gender: g}
		if err := repo.Create(p); err != nil {
			t.Errorf("failed to create patient with gender %s: %v", g, err)
		}
	}

	var count int64
	db.Model(&Patient{}).Count(&count)
	if count != 3 {
		t.Errorf("expected 3 patients, got %d", count)
	}
}
