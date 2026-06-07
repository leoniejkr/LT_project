package main

import (
	"fmt"
	"net/http"

	"backend/internal/dicom"
	"backend/internal/patient"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// @title           TrustAI API
// @version         1.0
// @description     API for upload of patient data and LLM analysis results
// @host            localhost:8080
// @BasePath        /
func main() {
	// connect to database
	dsn := "host=localhost user=user password=trustai dbname=trustai port=5432 sslmode=disable TimeZone=Europe/Berlin"
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		panic("failed to connect database")
	}

	// Automatische Migration der Tabellen
	db.AutoMigrate(&patient.Patient{})

	// DICOM Store initialisieren
	dicomStore, err := dicom.NewStore("./uploads/dicoms")
	if err != nil {
		panic("failed to create dicom store")
	}

	// set up api
	router := http.NewServeMux()

	patientRepo := patient.NewRepository(db)
	patientService := patient.NewService(patientRepo, dicomStore)
	patientHandler := patient.NewHandler(patientService)

	patientHandler.RegisterRoutes(router)

	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, "OK")
	})

	fmt.Println("Server starts on :8080")
	http.ListenAndServe(":8080", router)
}
