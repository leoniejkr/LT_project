package analysis

import (
	"testing"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupAnalysisDB(t *testing.T) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open test db: %v", err)
	}
	if err := db.AutoMigrate(&Analysis{}); err != nil {
		t.Fatalf("failed to migrate: %v", err)
	}
	return db
}

func TestCreate_Success(t *testing.T) {
	db := setupAnalysisDB(t)
	repo := NewRepository(db)

	a := &Analysis{
		PatientID:    1,
		Prediction:   "Pneumonia",
		Confidence:   0.92,
		Status:       "success",
		ModelVersion: "v1.0",
	}

	if err := repo.Create(a); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if a.ID == 0 {
		t.Error("expected ID to be set after create")
	}
}

func TestFindByPatientID_Found(t *testing.T) {
	db := setupAnalysisDB(t)
	repo := NewRepository(db)

	expected := &Analysis{
		PatientID:    42,
		Prediction:   "Effusion",
		Confidence:   0.88,
		Status:       "success",
		ModelVersion: "v1.0",
	}
	repo.Create(expected)

	found, err := repo.FindByPatientID(42)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if found.Prediction != "Effusion" {
		t.Errorf("prediction = %q, want %q", found.Prediction, "Effusion")
	}
	if found.Confidence != 0.88 {
		t.Errorf("confidence = %f, want 0.88", found.Confidence)
	}
}

func TestFindByPatientID_NotFound(t *testing.T) {
	db := setupAnalysisDB(t)
	repo := NewRepository(db)

	_, err := repo.FindByPatientID(999)
	if err == nil {
		t.Fatal("expected error for non-existent patient")
	}
}

func TestDeletePatientAnalysis(t *testing.T) {
	db := setupAnalysisDB(t)
	repo := NewRepository(db)

	repo.Create(&Analysis{PatientID: 1, Prediction: "A"})
	repo.Create(&Analysis{PatientID: 1, Prediction: "B"})
	repo.Create(&Analysis{PatientID: 2, Prediction: "C"})

	if err := repo.DeletePatientAnalysis(1); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	var count int64
	db.Model(&Analysis{}).Where("patient_id = ?", 1).Count(&count)
	if count != 0 {
		t.Errorf("expected 0 analyses for patient 1, got %d", count)
	}

	db.Model(&Analysis{}).Where("patient_id = ?", 2).Count(&count)
	if count != 1 {
		t.Errorf("expected 1 analysis for patient 2, got %d", count)
	}
}

func TestDeleteAll(t *testing.T) {
	db := setupAnalysisDB(t)
	repo := NewRepository(db)
	repo.Create(&Analysis{PatientID: 1, Prediction: "A"})
	repo.Create(&Analysis{PatientID: 2, Prediction: "B"})

	if err := repo.DeleteAll(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	var count int64
	db.Model(&Analysis{}).Count(&count)
	if count != 0 {
		t.Errorf("expected 0 analyses after delete all, got %d", count)
	}
}

func TestCreate_WithPredictions(t *testing.T) {
	db := setupAnalysisDB(t)
	repo := NewRepository(db)

	a := &Analysis{
		PatientID:    1,
		Prediction:   "Pneumonia",
		Confidence:   0.95,
		Status:       "success",
		ModelVersion: "v2.0",
		Predictions: Predictions{
			{Class: "Pneumonia", Confidence: 0.95, Reason: "Bilateral opacities"},
			{Class: "Effusion", Confidence: 0.78, Reason: "Fluid detected"},
		},
	}

	if err := repo.Create(a); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	found, err := repo.FindByPatientID(1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(found.Predictions) != 2 {
		t.Fatalf("expected 2 predictions, got %d", len(found.Predictions))
	}
}
