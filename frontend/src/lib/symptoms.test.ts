import { describe, expect, test } from 'vitest';
import {
	symptomLabelById,
	ALL_SYMPTOM_TAGS,
	SYMPTOM_TOPICS,
	type SymptomTag,
	type SymptomGroup,
} from './symptoms';

describe('symptomLabelById', () => {
	test('returns correct label for a known symptom id', () => {
		expect(symptomLabelById('dyspnea')).toBe('Shortness of breath (dyspnea)');
		expect(symptomLabelById('fever')).toBe('Fever (up to 105°F / 40°C)');
		expect(symptomLabelById('chest_pain')).toBe(
			'Chest pain, pressure, tightness, or heaviness',
		);
	});

	test('returns undefined for an unknown id', () => {
		expect(symptomLabelById('nonexistent_symptom')).toBeUndefined();
	});

	test('returns undefined for an empty string', () => {
		expect(symptomLabelById('')).toBeUndefined();
	});

	test('is case-sensitive — wrong casing returns undefined', () => {
		expect(symptomLabelById('Dyspnea')).toBeUndefined();
		expect(symptomLabelById('FEVER')).toBeUndefined();
	});
});

describe('ALL_SYMPTOM_TAGS', () => {
	test('contains every symptom from every topic and group', () => {
		const expected: SymptomTag[] = SYMPTOM_TOPICS.flatMap((t) =>
			t.groups.flatMap((g) => g.symptoms),
		);
		expect(ALL_SYMPTOM_TAGS).toEqual(expected);
	});

	test('has no duplicate ids', () => {
		const ids = ALL_SYMPTOM_TAGS.map((s) => s.id);
		const uniqueIds = new Set(ids);
		expect(ids.length).toBe(uniqueIds.size);
	});

	test('every tag has a non-empty id and label', () => {
		for (const tag of ALL_SYMPTOM_TAGS) {
			expect(tag.id).toBeTruthy();
			expect(tag.label).toBeTruthy();
			expect(typeof tag.id).toBe('string');
			expect(typeof tag.label).toBe('string');
		}
	});

	test('every id in ALL_SYMPTOM_TAGS can be resolved by symptomLabelById', () => {
		for (const tag of ALL_SYMPTOM_TAGS) {
			expect(symptomLabelById(tag.id)).toBe(tag.label);
		}
	});
});

describe('SYMPTOM_TOPICS structure', () => {
	test('every topic has a non-empty topic name', () => {
		for (const t of SYMPTOM_TOPICS) {
			expect(t.topic).toBeTruthy();
		}
	});

	test('every group has at least one symptom', () => {
		for (const t of SYMPTOM_TOPICS) {
			for (const g of t.groups) {
				expect(g.symptoms.length).toBeGreaterThan(0);
			}
		}
	});

	test('no two symptoms within the same group share an id', () => {
		for (const t of SYMPTOM_TOPICS) {
			for (const g of t.groups) {
				const ids = g.symptoms.map((s) => s.id);
				expect(new Set(ids).size).toBe(ids.length);
			}
		}
	});
});
