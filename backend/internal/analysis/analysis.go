package analysis

type Analysis struct {
	ID               uint    `gorm:"primaryKey" json:"id"`
	PatientID        uint    `gorm:"not null;index" json:"patientId"`
	Prediction       string  `json:"prediction"`
	Confidence       float64 `json:"confidence"`
	ConfidenceReason string  `json:"confidenceReason"`
	ModelVersion     string  `json:"modelVersion"`
	Status           string  `json:"status"`
}
