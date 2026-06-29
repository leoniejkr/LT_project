package analysis

type PredictionResponse struct {
	Status            string  `json:"status"`
	Prediction        string  `json:"prediction"`
	Confidence        float64 `json:"confidence"`
	Confidence_Reason string  `json:"confidence_reason"`
	ModelVersion      string  `json:"model_version"`
}

type LLMClient struct {
	baseURL string
}

// TODO: implementieren wenn modell steht
func NewLLMClient() *LLMClient {
	return nil
}

// TODO: implementieren wenn modell steht
func (c *LLMClient) GetPrediction(id uint) (*PredictionResponse, error) {
	return nil, nil
}
