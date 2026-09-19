// Package httpclient stellt einen schlanken HTTP-Client bereit, der von allen
// externen API-Integrationen genutzt wird (Ollama, Orthanc, Modelling-Service).
package httpclient

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

type Client struct {
	baseURL    string
	httpClient *http.Client
	username   string
	password   string
}

type Option func(*Client)

func WithHTTPClient(c *http.Client) Option {
	return func(cl *Client) { cl.httpClient = c }
}

func WithBasicAuth(username, password string) Option {
	return func(cl *Client) {
		cl.username = username
		cl.password = password
	}
}

func New(baseURL string, opts ...Option) *Client {
	cl := &Client{baseURL: baseURL, httpClient: &http.Client{}}
	for _, opt := range opts {
		opt(cl)
	}
	return cl
}

func (c *Client) Do(req *http.Request, out any) error {
	if c.username != "" && c.password != "" {
		req.SetBasicAuth(c.username, c.password)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request to %s failed: %w", req.URL, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("server returned status %d: %s", resp.StatusCode, string(body))
	}

	if out == nil {
		return nil
	}
	if err := json.Unmarshal(body, out); err != nil {
		return fmt.Errorf("failed to decode response: %w", err)
	}
	return nil
}

func (c *Client) PostJSON(path string, body any, out any) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return fmt.Errorf("failed to marshal request body: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, c.baseURL+path, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	return c.Do(req, out)
}

func (c *Client) Post(path, contentType string, body io.Reader, out any) error {
	req, err := http.NewRequest(http.MethodPost, c.baseURL+path, body)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", contentType)

	return c.Do(req, out)
}

// GetBytes fetches binary data from an external service while preserving its
// content type. It is used for image proxies where JSON decoding is unsuitable.
func (c *Client) GetBytes(path string) ([]byte, string, error) {
	req, err := http.NewRequest(http.MethodGet, c.baseURL+path, nil)
	if err != nil {
		return nil, "", fmt.Errorf("failed to create request: %w", err)
	}
	if c.username != "" && c.password != "" {
		req.SetBasicAuth(c.username, c.password)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, "", fmt.Errorf("request to %s failed: %w", req.URL, err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, "", fmt.Errorf("failed to read response body: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, "", fmt.Errorf("server returned status %d: %s", resp.StatusCode, string(body))
	}
	return body, resp.Header.Get("Content-Type"), nil
}
