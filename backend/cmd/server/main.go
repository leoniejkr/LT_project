package main

import (
	"fmt"
	"net/http"
)

func main() {
	router := http.NewServeMux()

	patientRepository := patient.NewRepository()

	patientHandler := patient.NewHandler(patientRepository)

	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, "OK")
	})

}
