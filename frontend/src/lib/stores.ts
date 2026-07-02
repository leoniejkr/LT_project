import { writable } from 'svelte/store';

export const analysisResult = writable<any>(null);
export const patientMetadata = writable<any>(null);
export const uploadedFileUrls = writable<string[]>([]);

