import { writable } from 'svelte/store';

export const analysisResult = writable<any>({
        status: "success",
        id: "PAT-12345",
        prediction: "Pneumonia detected",
        confidence: 0.875,
        confidence_reason: "Typical pneumonia as seen by state of lung.",
        model_version: "llm1"
    });

export const patientMetadata = writable<any>(null);
export const uploadedFileUrl = writable<string | null>(null);

