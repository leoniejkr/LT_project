package main

import (
	"fmt"
	"net/http"
	"os"

	"backend/internal/analysis"
	"backend/internal/api"
	"backend/internal/dicom"
	"backend/internal/patient"
	"backend/internal/platform"

	_ "backend/docs"

	httpSwagger "github.com/swaggo/http-swagger"
)

// @title           TrustAI API
// @version         1.0
// @description     API for upload of patient data and LLM analysis results
// @host            localhost:8080
// @BasePath        /
func main() {
	db, err := platform.InitDB()
	if err != nil {
		panic(fmt.Sprintf("failed to connect database: %v", err))
	}

	db.AutoMigrate(&patient.Patient{}, &analysis.Analysis{})

	router := http.NewServeMux()

	dicomRepo, err := dicom.NewRepository("./uploads/dicoms")
	patientRepo := patient.NewRepository(db)
	analysisRepo := analysis.NewRepository(db)
	llmClient := analysis.NewLLMClient()
	analysisService := analysis.NewService(analysisRepo, llmClient)
	patientService := patient.NewService(patientRepo, dicomRepo, analysisService)
	apiHandler := api.NewHandler(patientService, analysisService)
	apiHandler.RegisterRoutes(router)

	router.Handle("/swagger/", httpSwagger.WrapHandler)

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
