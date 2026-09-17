import { describe, expect, test, vi } from 'vitest';
import { get } from 'svelte/store';
import { analysisResult, patientMetadata, imageUrls } from './stores';
import type { AnalysisResult, AnalysisResponse, PatientMetadata } from './types';

function mockAnalysisResponse(overrides: Partial<AnalysisResponse> = {}): AnalysisResponse {
	return {
		status: 'success',
		model_version: 'v1.0',
		predictions: [],
		image_results: [],
		...overrides,
	};
}

function mockAnalysisResult(overrides: Partial<AnalysisResult> = {}): AnalysisResult {
	return {
		status: 'success',
		patient: {
			id: 1,
			age: 45,
			gender: 'male',
			symptoms: ['dyspnea'],
			history: ['smoking_tobacco'],
			orthancIDs: ['orthanc-1'],
		},
		analysis: mockAnalysisResponse(),
		...overrides,
	};
}

describe('analysisResult store', () => {
	test('initializes to null', () => {
		expect(get(analysisResult)).toBeNull();
	});

	test('accepts and returns a full AnalysisResult', () => {
		const result = mockAnalysisResult();
		analysisResult.set(result);
		expect(get(analysisResult)).toEqual(result);
	});

	test('resets to null', () => {
		analysisResult.set(mockAnalysisResult());
		analysisResult.set(null);
		expect(get(analysisResult)).toBeNull();
	});

	test('notifies subscribers on update', () => {
		const values: (AnalysisResult | null)[] = [];
		const unsub = analysisResult.subscribe((v) => values.push(v));

		const result = mockAnalysisResult();
		analysisResult.set(result);
		analysisResult.set(null);

		expect(values).toEqual([null, result, null]);
		unsub();
	});

	test('update fn transforms current value', () => {
		analysisResult.set(mockAnalysisResult({ status: 'pending' }));
		analysisResult.update((prev) => {
			if (!prev) return null;
			return { ...prev, status: 'completed' };
		});
		expect(get(analysisResult)?.status).toBe('completed');
	});
});

describe('patientMetadata store', () => {
	test('initializes to null', () => {
		expect(get(patientMetadata)).toBeNull();
	});

	test('accepts patient metadata objects', () => {
		const meta: PatientMetadata = {
			age: 60,
			gender: 'male',
			symptoms: [],
			history: [],
		};
		patientMetadata.set(meta);
		expect(get(patientMetadata)).toEqual(meta);
	});

	test('resets to null', () => {
		patientMetadata.set({
			age: 45,
			gender: 'female',
			symptoms: ['dyspnea'],
			history: [],
		});
		patientMetadata.set(null);
		expect(get(patientMetadata)).toBeNull();
	});
});

describe('imageUrls store', () => {
	test('initializes to empty array', () => {
		expect(get(imageUrls)).toEqual([]);
	});

	test('stores multiple file urls', () => {
		const urls = ['http://localhost/file1.png', 'http://localhost/file2.png'];
		imageUrls.set(urls);
		expect(get(imageUrls)).toEqual(urls);
	});

	test('update fn can append urls', () => {
		imageUrls.set([]);
		imageUrls.update((prev) => [...prev, 'http://localhost/new.png']);
		imageUrls.update((prev) => [...prev, 'http://localhost/another.png']);
		expect(get(imageUrls)).toEqual([
			'http://localhost/new.png',
			'http://localhost/another.png',
		]);
	});

	test('reset to empty array', () => {
		imageUrls.set(['http://localhost/old.png']);
		imageUrls.set([]);
		expect(get(imageUrls)).toEqual([]);
	});
});
