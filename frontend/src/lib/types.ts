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
}

export interface PatientMetadata {
    age: number;
    gender: string;
    symptoms: string[];
    history: string[];
}

export interface PatientData extends PatientMetadata {
    id: number;
    orthancIDs: string[];
}

export interface AnalysisResult {
    status: string;
    patient: PatientData;
    analysis: AnalysisResponse;
}

export interface CategorizedPrediction {
    pred: Prediction;
    rank: number;
}
