package main

import (
	"fmt"
	"io"
	"net/http"
)

func main() {
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintln(w, "OK")
	})

	http.HandleFunc("/test-modelling", func(w http.ResponseWriter, r *http.Request) {
		resp, err := http.Post("http://modelling:5000/predict", "application/json", nil)
		if err != nil {
			http.Error(w, fmt.Sprintf("Failed to reach modelling: %v", err), 500)
			return
		}
		defer resp.Body.Close()
		w.Header().Set("Content-Type", "application/json")
		io.Copy(w, resp.Body)
	})

	fmt.Println("Server starting on :4000...")
	if err := http.ListenAndServe(":4000", nil); err != nil {
		fmt.Printf("Error starting server: %s\n", err)
	}
}
