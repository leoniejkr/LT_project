package httpclient

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestPostJSON_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.URL.Path != "/api/test" {
			t.Errorf("expected /api/test, got %s", r.URL.Path)
		}
		if ct := r.Header.Get("Content-Type"); ct != "application/json" {
			t.Errorf("expected application/json, got %s", ct)
		}

		body, _ := io.ReadAll(r.Body)
		var sent map[string]any
		if err := json.Unmarshal(body, &sent); err != nil {
			t.Fatalf("request body is not valid json: %v", err)
		}
		if sent["name"] != "foo" {
			t.Errorf("name = %v, want foo", sent["name"])
		}

		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"result": "bar"}`))
	}))
	defer server.Close()

	client := New(server.URL)

	var result struct {
		Result string `json:"result"`
	}
	if err := client.PostJSON("/api/test", map[string]string{"name": "foo"}, &result); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Result != "bar" {
		t.Errorf("result = %q, want %q", result.Result, "bar")
	}
}

func TestPostJSON_MarshalError(t *testing.T) {
	client := New("http://localhost:1")

	ch := make(chan int)
	err := client.PostJSON("/api/test", ch, nil)
	if err == nil {
		t.Fatal("expected error for marshal failure")
	}
	if !strings.Contains(err.Error(), "marshal") {
		t.Errorf("error should mention marshal, got: %v", err)
	}
}

func TestPostJSON_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("exploded"))
	}))
	defer server.Close()

	client := New(server.URL)

	err := client.PostJSON("/api/test", map[string]string{"name": "foo"}, nil)
	if err == nil {
		t.Fatal("expected error for server error response")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Errorf("error should contain status 500, got: %v", err)
	}
	if !strings.Contains(err.Error(), "exploded") {
		t.Errorf("error should contain response body, got: %v", err)
	}
}

func TestPostJSON_InvalidJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte("not json"))
	}))
	defer server.Close()

	client := New(server.URL)

	var result map[string]any
	err := client.PostJSON("/api/test", map[string]string{"name": "foo"}, &result)
	if err == nil {
		t.Fatal("expected error for invalid JSON response")
	}
	if !strings.Contains(err.Error(), "decode") {
		t.Errorf("error should mention decode failure, got: %v", err)
	}
}

func TestDo_NoDecodeOnNil(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := New(server.URL)

	if err := client.PostJSON("/api/test", map[string]string{"name": "foo"}, nil); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDo_BasicAuth(t *testing.T) {
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
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := New(server.URL, WithBasicAuth("admin", "secret"))

	if err := client.PostJSON("/api/test", map[string]string{"name": "foo"}, nil); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDo_NoBasicAuth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _, ok := r.BasicAuth()
		if ok {
			t.Error("expected no basic auth")
		}
		w.Write([]byte(`{}`))
	}))
	defer server.Close()

	client := New(server.URL)

	if err := client.PostJSON("/api/test", map[string]string{"name": "foo"}, nil); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestPost_CustomContentType(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if ct := r.Header.Get("Content-Type"); !strings.HasPrefix(ct, "multipart/form-data") {
			t.Errorf("expected multipart content type, got %s", ct)
		}
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), "hello") {
			t.Errorf("body should contain payload, got: %s", string(body))
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ok": true}`))
	}))
	defer server.Close()

	client := New(server.URL)

	var result struct {
		OK bool `json:"ok"`
	}
	err := client.Post("/predict", "multipart/form-data; boundary=abc", bytes.NewReader([]byte("hello")), &result)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result.OK {
		t.Error("expected ok = true")
	}
}

func TestDo_ConnectionRefused(t *testing.T) {
	client := New("http://localhost:1", WithHTTPClient(&http.Client{Timeout: time.Second}))

	err := client.PostJSON("/api/test", map[string]string{"name": "foo"}, nil)
	if err == nil {
		t.Fatal("expected error for connection refused")
	}
}

func TestNew_DefaultHTTPClient(t *testing.T) {
	client := New("http://localhost:1")
	if client.httpClient == nil {
		t.Error("expected a default http client")
	}
}