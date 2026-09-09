import { writable } from 'svelte/store';
import type { AnalysisResult, PatientMetadata } from './types';

export const analysisResult = writable<AnalysisResult | null>(null);
export const patientMetadata = writable<PatientMetadata | null>(null);
export const uploadedFileUrls = writable<string[]>([]);
