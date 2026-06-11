package main

import (
	"fmt"
	"net/http"
	"os"

	"backend/internal/dicom"
	"backend/internal/patient"
	"backend/internal/platform"
)

// @title           TrustAI API
// @version         1.0
// @description     API for upload of patient data and LLM analysis results
// @host            localhost:8080
// @BasePath        /
func main() {
	// connect to database
	db, err := platform.InitDB()
	if err != nil {
		panic(fmt.Sprintf("failed to connect database: %v", err))
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

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	fmt.Printf("Server starts on :%s\n", port)
	http.ListenAndServe(":"+port, router)
}
