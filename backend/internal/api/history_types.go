package api

type PatientSummary struct {
	ID     uint   `json:"id"`
	Age    uint   `json:"age"`
	Gender string `json:"gender"`
}

type PatientAnalysisResponse struct {
	Status   string           `json:"status"`
	Patient  *PatientResponse `json:"patient"`
	Analysis AnalysisResponse `json:"analysis"`
}
