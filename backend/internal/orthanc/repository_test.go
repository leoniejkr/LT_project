package orthanc

import (
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestStoreXRays_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/tools/create-dicom" {
			t.Errorf("expected /tools/create-dicom, got %s", r.URL.Path)
		}
		if ct := r.Header.Get("Content-Type"); ct != "application/json" {
			t.Errorf("expected application/json, got %s", ct)
		}

		body, _ := io.ReadAll(r.Body)
		var payload map[string]any
		if err := json.Unmarshal(body, &payload); err != nil {
			t.Fatalf("failed to parse request body: %v", err)
		}

		content, ok := payload["Content"].(string)
		if !ok || !strings.HasPrefix(content, "data:image/png;base64,") {
			t.Errorf("unexpected Content format: %v", payload["Content"])
		}

		tags, ok := payload["Tags"].(map[string]any)
		if !ok {
			t.Fatal("missing Tags in request")
		}
		if tags["PatientName"] != "Patient_1" {
			t.Errorf("PatientName = %v, want Patient_1", tags["PatientName"])
		}
		if tags["PatientID"] != "42" {
			t.Errorf("PatientID = %v, want 42", tags["PatientID"])
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ID": "instance-123"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	instanceID, err := repo.StoreXRays("Patient_1", "42", []byte("fake-png"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if instanceID != "instance-123" {
		t.Errorf("instanceID = %q, want %q", instanceID, "instance-123")
	}
}

func TestStoreXRays_Base64Encoding(t *testing.T) {
	pngData := []byte("real-png-bytes")
	expectedEncoded := base64.StdEncoding.EncodeToString(pngData)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload map[string]any
		json.Unmarshal(body, &payload)

		content := payload["Content"].(string)
		expected := "data:image/png;base64," + expectedEncoded
		if content != expected {
			t.Errorf("Content does not match expected base64 encoding")
		}

		w.Write([]byte(`{"ID": "test-id"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	_, err := repo.StoreXRays("P", "1", pngData)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestStoreXRays_WithAuth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		user, pass, ok := r.BasicAuth()
		if !ok {
			t.Error("expected basic auth to be set")
		}
		if user != "admin" {
			t.Errorf("username = %q, want %q", user, "admin")
		}
		if pass != "secret" {
			t.Errorf("password = %q, want %q", pass, "secret")
		}
		w.Write([]byte(`{"ID": "auth-id"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "admin", "secret")
	_, err := repo.StoreXRays("P", "1", []byte("data"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestStoreXRays_WithoutAuth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _, ok := r.BasicAuth()
		if ok {
			t.Error("expected no basic auth")
		}
		w.Write([]byte(`{"ID": "no-auth-id"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	_, err := repo.StoreXRays("P", "1", []byte("data"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestStoreXRays_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("orthanc down"))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	_, err := repo.StoreXRays("P", "1", []byte("data"))
	if err == nil {
		t.Fatal("expected error for server error")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Errorf("error should contain status 500, got: %v", err)
	}
}

func TestStoreXRays_InvalidJSONResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("not json"))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	_, err := repo.StoreXRays("P", "1", []byte("data"))
	if err == nil {
		t.Fatal("expected error for invalid JSON response")
	}
}

func TestStoreXRays_ConnectionRefused(t *testing.T) {
	repo := NewRepository("http://localhost:1", "", "")
	_, err := repo.StoreXRays("P", "1", []byte("data"))
	if err == nil {
		t.Fatal("expected error for connection refused")
	}
}

func TestStoreXRays_DICOMTags(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload map[string]any
		json.Unmarshal(body, &payload)

		tags := payload["Tags"].(map[string]any)
		if tags["StudyDescription"] != "Uploaded XRays" {
			t.Errorf("StudyDescription = %v, want 'Uploaded XRays'", tags["StudyDescription"])
		}
		if tags["Modality"] != "XC" {
			t.Errorf("Modality = %v, want XC", tags["Modality"])
		}

		w.Write([]byte(`{"ID": "dicom-id"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	_, err := repo.StoreXRays("P", "1", []byte("data"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
