package orthanc

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func makeTestPNG(t *testing.T) []byte {
	t.Helper()
	img := image.NewGray(image.Rect(0, 0, 4, 4))
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("failed to create test png: %v", err)
	}
	return buf.Bytes()
}

func makeTestPalettePNG(t *testing.T) []byte {
	t.Helper()
	palette := color.Palette{color.Black, color.White}
	img := image.NewPaletted(image.Rect(0, 0, 4, 4), palette)
	for y := 0; y < 4; y++ {
		for x := 0; x < 4; x++ {
			img.Set(x, y, palette[(x+y)%2])
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatalf("failed to create palette test png: %v", err)
	}
	return buf.Bytes()
}

func makeTestJPEG(t *testing.T) []byte {
	t.Helper()
	img := image.NewGray(image.Rect(0, 0, 4, 4))
	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, img, nil); err != nil {
		t.Fatalf("failed to create test jpeg: %v", err)
	}
	return buf.Bytes()
}

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
	instanceID, err := repo.StoreXRays("Patient_1", "42", makeTestPNG(t))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if instanceID != "instance-123" {
		t.Errorf("instanceID = %q, want %q", instanceID, "instance-123")
	}
}

func TestStoreXRays_Base64Encoding(t *testing.T) {
	pngData := makeTestPNG(t)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload map[string]any
		json.Unmarshal(body, &payload)

		content, ok := payload["Content"].(string)
		if !ok || !strings.HasPrefix(content, "data:image/png;base64,") {
			t.Fatalf("unexpected Content format: %v", payload["Content"])
		}

		raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(content, "data:image/png;base64,"))
		if err != nil {
			t.Fatalf("Content is not valid base64: %v", err)
		}
		if _, err := png.Decode(bytes.NewReader(raw)); err != nil {
			t.Fatalf("Content is not a valid png: %v", err)
		}

		w.Write([]byte(`{"ID": "test-id"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	if _, err := repo.StoreXRays("P", "1", pngData); err != nil {
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
	_, err := repo.StoreXRays("P", "1", makeTestPNG(t))
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
	_, err := repo.StoreXRays("P", "1", makeTestPNG(t))
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
	_, err := repo.StoreXRays("P", "1", makeTestPNG(t))
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
	_, err := repo.StoreXRays("P", "1", makeTestPNG(t))
	if err == nil {
		t.Fatal("expected error for invalid JSON response")
	}
}

func TestStoreXRays_ConnectionRefused(t *testing.T) {
	repo := NewRepository("http://localhost:1", "", "")
	_, err := repo.StoreXRays("P", "1", makeTestPNG(t))
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
	_, err := repo.StoreXRays("P", "1", makeTestPNG(t))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestStoreXRays_FlattensPalettePNG(t *testing.T) {
	var received []byte
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload map[string]any
		json.Unmarshal(body, &payload)

		content := payload["Content"].(string)
		raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(content, "data:image/png;base64,"))
		if err != nil {
			t.Fatalf("invalid base64: %v", err)
		}
		received = raw
		w.Write([]byte(`{"ID": "flat-id"}`))
	}))
	defer server.Close()

	palettePNG := makeTestPalettePNG(t)

	cfg, _, err := image.DecodeConfig(bytes.NewReader(palettePNG))
	if err != nil {
		t.Fatalf("fixture should be a valid png: %v", err)
	}
	if _, isPalette := cfg.ColorModel.(color.Palette); !isPalette {
		t.Fatal("fixture should be a palette png")
	}

	repo := NewRepository(server.URL, "", "")
	if _, err := repo.StoreXRays("P", "1", palettePNG); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	cfg, format, err := image.DecodeConfig(bytes.NewReader(received))
	if err != nil {
		t.Fatalf("stored content should be a valid png: %v", err)
	}
	if format != "png" {
		t.Errorf("format = %q, want png", format)
	}
	if _, isPalette := cfg.ColorModel.(color.Palette); isPalette {
		t.Error("palette should have been flattened, but stored png is still paletted")
	}
}

func TestStoreXRays_AcceptsJPEG(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var payload map[string]any
		json.Unmarshal(body, &payload)

		content := payload["Content"].(string)
		raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(content, "data:image/png;base64,"))
		if err != nil {
			t.Fatalf("invalid base64: %v", err)
		}
		cfg, format, err := image.DecodeConfig(bytes.NewReader(raw))
		if err != nil {
			t.Fatalf("jpeg input was not converted to a readable image: %v", err)
		}
		if format != "png" {
			t.Errorf("format = %q, want converted png", format)
		}
		if cfg.Width != 4 || cfg.Height != 4 {
			t.Errorf("size = %dx%d, want 4x4", cfg.Width, cfg.Height)
		}

		w.Write([]byte(`{"ID": "jpeg-id"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	if _, err := repo.StoreXRays("P", "1", makeTestJPEG(t)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestStoreXRays_RejectsInvalidImageData(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("orthanc should not be called with invalid image data")
		w.Write([]byte(`{"ID": "never"}`))
	}))
	defer server.Close()

	repo := NewRepository(server.URL, "", "")
	_, err := repo.StoreXRays("P", "1", []byte("this-is-not-an-image"))
	if err == nil {
		t.Fatal("expected error for invalid image data")
	}
	if !strings.Contains(err.Error(), "unsupported image data") {
		t.Errorf("error should mention unsupported image data, got: %v", err)
	}
}

func TestGetPreview(t *testing.T) {
	want := []byte("preview-image")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("method = %s, want GET", r.Method)
		}
		if r.URL.Path != "/instances/instance-123/preview" {
			t.Errorf("path = %q, want preview path", r.URL.Path)
		}
		w.Header().Set("Content-Type", "image/png")
		w.Write(want)
	}))
	defer server.Close()

	got, contentType, err := NewRepository(server.URL, "", "").GetPreview("instance-123")
	if err != nil {
		t.Fatalf("GetPreview returned error: %v", err)
	}
	if !bytes.Equal(got, want) {
		t.Errorf("preview = %q, want %q", got, want)
	}
	if contentType != "image/png" {
		t.Errorf("content type = %q, want image/png", contentType)
	}
}
