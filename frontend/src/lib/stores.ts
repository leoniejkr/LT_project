import { writable } from 'svelte/store';
import type { AnalysisResult } from './types';

export const analysisResult = writable<AnalysisResult>;
export const patientMetadata = writable<any>(null);
export const uploadedFileUrls = writable<string[]>([]);
