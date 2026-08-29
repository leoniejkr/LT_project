import { describe, expect, test } from 'vitest';
import { cn } from './utils';

describe('cn', () => {
	test('merges class names', () => {
		expect(cn('foo', 'bar')).toBe('foo bar');
	});

	test('deduplicates identical tailwind classes', () => {
		expect(cn('px-2', 'px-2')).toBe('px-2');
	});

	test('resolves conflicting tailwind classes', () => {
		expect(cn('px-2', 'px-4')).toBe('px-4');
	});

	test('handles conditional classes', () => {
		expect(cn('foo', false && 'bar')).toBe('foo');
		expect(cn('foo', true && 'bar')).toBe('foo bar');
	});

	test('handles undefined and empty', () => {
		expect(cn('foo', undefined, null)).toBe('foo');
		expect(cn()).toBe('');
	});
});
