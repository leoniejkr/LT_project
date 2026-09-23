package api

import (
	"backend/internal/analysis"
	"encoding/json"
	"strings"
	"testing"
)

func TestAnalysisResponseDoesNotExposeHeatmapBase64(t *testing.T) {
	response := newAnalysisResponse("success", "v1", nil, analysis.ImageResults{
		{
			Index:    0,
			Filename: "xray.png",
			Predictions: analysis.ImagePredictions{
				{Class: "Pneumonia", Confidence: 0.91, Heatmap: "base64-png-data", OrthancID: "heatmap-id"},
			},
		},
	})

	data, err := json.Marshal(response)
	if err != nil {
		t.Fatalf("marshal response: %v", err)
	}
	if strings.Contains(string(data), `"heatmap"`) {
		t.Errorf("public response must not contain a heatmap payload: %s", data)
	}
	if !strings.Contains(string(data), `"orthancId":"heatmap-id"`) {
		t.Errorf("public response must retain the Orthanc reference: %s", data)
	}
}
