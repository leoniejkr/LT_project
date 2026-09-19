import { beforeEach, describe, expect, test } from 'vitest';
import { get } from 'svelte/store';
import {
	customThreshold,
	decisionMode,
	effectiveThreshold,
	setCustomThreshold,
} from './settings';

beforeEach(() => {
	customThreshold.set(50);
	decisionMode.set('balanced');
});

describe('setCustomThreshold', () => {
	test('switches from a preset to custom mode', () => {
		setCustomThreshold(67);

		expect(get(decisionMode)).toBe('custom');
		expect(get(customThreshold)).toBe(67);
		expect(get(effectiveThreshold)).toBe(67);
	});

	test.each([
		[-10, 0],
		[101, 100],
		[42.6, 43],
	])('normalizes %s to %s', (value, expected) => {
		setCustomThreshold(value);

		expect(get(customThreshold)).toBe(expected);
	});
});
