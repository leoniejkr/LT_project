package main

import (
	"fmt"
	"net/http"
	"os"

	"backend/internal/analysis"
	"backend/internal/api"
	"backend/internal/chat"
	"backend/internal/orthanc"
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

	orthancURL := os.Getenv("ORTHANC_URL")
	if orthancURL == "" {
		orthancURL = "http://localhost:8042"
	}

	ollamaURL := os.Getenv("OLLAMA_URL")
	if ollamaURL == "" {
		ollamaURL = "http://localhost:11434"
	}

	model := os.Getenv("LLM_MODEL")

	orthancStore := orthanc.NewRepository(orthancURL, "user", "user")
	patientRepo := patient.NewRepository(db)
	analysisRepo := analysis.NewRepository(db)
	llmClient := analysis.NewLLMClient()
	analysisService := analysis.NewService(analysisRepo, llmClient)
	patientService := patient.NewService(patientRepo, analysisService, orthancStore)
	chatService := chat.NewService(ollamaURL, model, nil)
	apiHandler := api.NewHandler(patientService, chatService, analysisService)
	apiHandler.RegisterRoutes(router)

	router.Handle("/swagger/", httpSwagger.WrapHandler)

	// Health godoc
	// @Summary      Health check
	// @Description  Returns OK if the server is running
	// @Tags         health
	// @Produce      plain
	// @Success      200  {string}  string  "OK"
	// @Router       /health [get]
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
