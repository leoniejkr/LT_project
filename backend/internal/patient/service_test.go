package patient

import (
	"backend/internal/orthanc"
	"bytes"
	"image"
	"image/png"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func testPNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewGray(image.Rect(0, 0, 4, 4))
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("failed to create test png: %v", err)
	}
	return buf.Bytes()
}

func setupServiceDeps(t *testing.T) (*Service, *httptest.Server) {
	t.Helper()

	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatalf("failed to open test db: %v", err)
	}
	db.AutoMigrate(&Patient{})

	orthancServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"ID": "orthanc-instance-1"}`))
	}))

	patientRepo := NewRepository(db)
	orthancRepo := orthanc.NewRepository(orthancServer.URL, "", "")
	patientSvc := NewService(patientRepo, orthancRepo)

	return patientSvc, orthancServer
}

func TestCreatePatient_NoFiles(t *testing.T) {
	svc, orthancSrv := setupServiceDeps(t)
	defer orthancSrv.Close()

	p := &Patient{Age: 55, Gender: GenderMale}
	result, err := svc.CreatePatient(p, nil)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.ID == 0 {
		t.Error("expected ID to be set")
	}
	if result.Age != 55 {
		t.Errorf("age = %d, want 55", result.Age)
	}
}

func TestCreatePatient_WithFiles(t *testing.T) {
	svc, orthancSrv := setupServiceDeps(t)
	defer orthancSrv.Close()

	p := &Patient{Age: 30, Gender: GenderFemale}
	files := []FileInput{
		{Name: "xray1.png", Bytes: testPNG(t)},
		{Name: "xray2.png", Bytes: testPNG(t)},
	}

	result, err := svc.CreatePatient(p, files)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result.OrthancIDs) != 2 {
		t.Errorf("orthanc ids len = %d, want 2", len(result.OrthancIDs))
	}
}

func TestCreatePatient_OrthancError(t *testing.T) {
	orthancServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer orthancServer.Close()

	db, _ := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	db.AutoMigrate(&Patient{})

	patientRepo := NewRepository(db)
	orthancRepo := orthanc.NewRepository(orthancServer.URL, "", "")
	svc := NewService(patientRepo, orthancRepo)

	p := &Patient{Age: 40, Gender: GenderMale}
	files := []FileInput{{Name: "img.png", Bytes: testPNG(t)}}

	_, err := svc.CreatePatient(p, files)
	if err == nil {
		t.Fatal("expected error when orthanc fails")
	}
}

func TestGetPatient(t *testing.T) {
	svc, orthancSrv := setupServiceDeps(t)
	defer orthancSrv.Close()

	p := &Patient{Age: 70, Gender: GenderDiverse, History: Histories{History("Asthma, COPD, or Emphysema")}}
	svc.CreatePatient(p, nil)

	found, err := svc.GetPatient(p.ID)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if found.Age != 70 {
		t.Errorf("age = %d, want 70", found.Age)
	}
	if found.Gender != GenderDiverse {
		t.Errorf("gender = %q, want %q", found.Gender, GenderDiverse)
	}
}

func TestServiceDeleteAll(t *testing.T) {
	svc, orthancSrv := setupServiceDeps(t)
	defer orthancSrv.Close()

	svc.CreatePatient(&Patient{Age: 20, Gender: GenderMale}, nil)
	svc.CreatePatient(&Patient{Age: 30, Gender: GenderFemale}, nil)

	if err := svc.DeleteAll(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	var count int64
	svc.repo.db.Model(&Patient{}).Count(&count)
	if count != 0 {
		t.Errorf("expected 0 patients, got %d", count)
	}
}
