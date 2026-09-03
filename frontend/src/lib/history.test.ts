import { describe, expect, test } from 'vitest';
import {
	historyLabelById,
	ALL_HISTORY_TAGS,
	HISTORY_TOPICS,
	type HistoryTag,
} from './history';

describe('historyLabelById', () => {
	test('returns correct label for a known history id', () => {
		expect(historyLabelById('smoking_tobacco')).toBe('Smoking tobacco / cigarettes');
		expect(historyLabelById('heart_disease')).toBe(
			'Heart attack or history of heart disease',
		);
		expect(historyLabelById('asthma_copd')).toBe('Asthma, COPD, or Emphysema');
	});

	test('returns undefined for an unknown id', () => {
		expect(historyLabelById('nonexistent_risk_factor')).toBeUndefined();
	});

	test('returns undefined for an empty string', () => {
		expect(historyLabelById('')).toBeUndefined();
	});

	test('is case-sensitive — wrong casing returns undefined', () => {
		expect(historyLabelById('Smoking_Tobacco')).toBeUndefined();
		expect(historyLabelById('HEART_DISEASE')).toBeUndefined();
	});
});

describe('ALL_HISTORY_TAGS', () => {
	test('contains every history tag from every topic and group', () => {
		const expected: HistoryTag[] = HISTORY_TOPICS.flatMap((t) =>
			t.groups.flatMap((g) => g.symptoms),
		);
		expect(ALL_HISTORY_TAGS).toEqual(expected);
	});

	test('has no duplicate ids', () => {
		const ids = ALL_HISTORY_TAGS.map((t) => t.id);
		const uniqueIds = new Set(ids);
		expect(ids.length).toBe(uniqueIds.size);
	});

	test('every tag has a non-empty id and label', () => {
		for (const tag of ALL_HISTORY_TAGS) {
			expect(tag.id).toBeTruthy();
			expect(tag.label).toBeTruthy();
			expect(typeof tag.id).toBe('string');
			expect(typeof tag.label).toBe('string');
		}
	});

	test('every id in ALL_HISTORY_TAGS can be resolved by historyLabelById', () => {
		for (const tag of ALL_HISTORY_TAGS) {
			expect(historyLabelById(tag.id)).toBe(tag.label);
		}
	});
});

describe('HISTORY_TOPICS structure', () => {
	test('every topic has a non-empty topic name', () => {
		for (const t of HISTORY_TOPICS) {
			expect(t.topic).toBeTruthy();
		}
	});

	test('every group has at least one symptom', () => {
		for (const t of HISTORY_TOPICS) {
			for (const g of t.groups) {
				expect(g.symptoms.length).toBeGreaterThan(0);
			}
		}
	});

	test('no two tags within the same group share an id', () => {
		for (const t of HISTORY_TOPICS) {
			for (const g of t.groups) {
				const ids = g.symptoms.map((s) => s.id);
				expect(new Set(ids).size).toBe(ids.length);
			}
		}
	});
});
