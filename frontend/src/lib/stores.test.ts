import { describe, expect, test, vi } from 'vitest';
import { get } from 'svelte/store';
import { analysisResult, patientMetadata, uploadedFileUrls } from './stores';
import type { AnalysisResult, AnalysisResponse } from './types';

function mockAnalysisResponse(overrides: Partial<AnalysisResponse> = {}): AnalysisResponse {
	return {
		status: 'success',
		model_version: 'v1.0',
		predictions: [],
		image_results: [],
		is_mock: false,
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

	test('accepts arbitrary metadata objects', () => {
		const meta = { name: 'John Doe', age: 60, note: 'follow-up' };
		patientMetadata.set(meta);
		expect(get(patientMetadata)).toEqual(meta);
	});

	test('resets to null', () => {
		patientMetadata.set({ something: true });
		patientMetadata.set(null);
		expect(get(patientMetadata)).toBeNull();
	});
});

describe('uploadedFileUrls store', () => {
	test('initializes to empty array', () => {
		expect(get(uploadedFileUrls)).toEqual([]);
	});

	test('stores multiple file urls', () => {
		const urls = ['http://localhost/file1.png', 'http://localhost/file2.png'];
		uploadedFileUrls.set(urls);
		expect(get(uploadedFileUrls)).toEqual(urls);
	});

	test('update fn can append urls', () => {
		uploadedFileUrls.set([]);
		uploadedFileUrls.update((prev) => [...prev, 'http://localhost/new.png']);
		uploadedFileUrls.update((prev) => [...prev, 'http://localhost/another.png']);
		expect(get(uploadedFileUrls)).toEqual([
			'http://localhost/new.png',
			'http://localhost/another.png',
		]);
	});

	test('reset to empty array', () => {
		uploadedFileUrls.set(['http://localhost/old.png']);
		uploadedFileUrls.set([]);
		expect(get(uploadedFileUrls)).toEqual([]);
	});
});
