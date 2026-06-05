package main

import (
	"fmt"
	"net/http"
)

// @title           TrustAI API
// @version         1.0
// @description     API for upload of patient data and LLM analysis results
// @host            localhost:8080
// @BasePath        /
func main() {
	router := http.NewServeMux()

	patientRepository := patient.NewRepository()

	patientHandler := patient.NewHandler(patientRepository)

	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, "OK")
	})

}
