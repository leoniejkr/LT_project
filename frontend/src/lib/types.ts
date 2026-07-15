export interface Prediction {
    class: string;
    confidence: number;
    reason?: string;
}

export interface ImagePrediction {
    class: string;
    confidence: number;
    heatmap: string;
}

export interface ImageResult {
    index: number;
    filename: string;
    predictions: ImagePrediction[];
}

export interface AnalysisResponse {
    status: string;
    model_version: string;
    predictions: Prediction[];
    image_results: ImageResult[];
    is_mock: boolean;
}

export interface PatientData {
    id: number;
    age: number;
    gender: string;
    knownIllnesses: string[];
    symptoms: string[];
    orthancIDs: string[];
}

export interface AnalysisResult {
    status: string;
    patient: PatientData;
    analysis: AnalysisResponse;
}
