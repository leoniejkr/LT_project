import type { AnalysisResult, ImageResult } from "$lib/types";

export function patientImageUrl(patientId: number, orthancId: string): string {
    return `/api/patients/${patientId}/images/${orthancId}`;
}

// Orthanc instance IDs are the durable source for originals and heatmaps.
// Replace transient base64 payloads with backend URLs before rendering them.
export function withPersistedImageUrls(result: AnalysisResult): AnalysisResult {
    const patientId = result.patient.id;
    return {
        ...result,
        analysis: {
            ...result.analysis,
            image_results: result.analysis.image_results.map((image: ImageResult) => ({
                ...image,
                predictions: image.predictions.map((prediction) => ({
                    ...prediction,
                    heatmap: prediction.orthancId
                        ? patientImageUrl(patientId, prediction.orthancId)
                        : undefined,
                })),
            })),
        },
    };
}
