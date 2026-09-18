import { beforeEach, describe, expect, test, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/dom';
import navigation from './navigation.svelte';

const { holder } = vi.hoisted(() => ({
	holder: {
		pathname: '/',
		toggleMode: vi.fn(),
	},
}));

vi.mock('$app/state', () => ({
	get page() {
		return { url: new URL(`http://localhost${holder.pathname}`) };
	},
}));

vi.mock('mode-watcher', () => ({
	toggleMode: () => holder.toggleMode(),
}));

beforeEach(() => {
	holder.pathname = '/';
	holder.toggleMode.mockClear();
});

describe('navigation.svelte', () => {
	test('renders all primary links', () => {
		render(navigation);
		for (const name of ['Home', 'Upload', 'Result', 'History']) {
			expect(screen.getByRole('link', { name })).toBeTruthy();
		}
	});

	test('marks Home as active only on the root path', () => {
		holder.pathname = '/';
		render(navigation);
		const home = screen.getByRole('link', { name: 'Home' });
		expect(home.className).toContain('bg-muted');
		expect(home.getAttribute('aria-current')).toBe('page');
	});

	test('marks Upload as active on an upload path', () => {
		holder.pathname = '/upload';
		render(navigation);
		const upload = screen.getByRole('link', { name: 'Upload' });
		expect(upload.className).toContain('bg-muted');
		expect(upload.getAttribute('aria-current')).toBe('page');
	});

	test('does not mark Home active on subpaths', () => {
		holder.pathname = '/result';
		render(navigation);
		const home = screen.getByRole('link', { name: 'Home' });
		expect(home.className).not.toContain('bg-muted');
		expect(home.hasAttribute('aria-current')).toBe(false);
	});

	test('links to the result page', () => {
		render(navigation);
		const result = screen.getByRole('link', { name: 'Result' });
		expect(result.getAttribute('href')).toBe('/result');
	});

	test('links to the upload page', () => {
		render(navigation);
		const upload = screen.getByRole('link', { name: 'Upload' });
		expect(upload.getAttribute('href')).toBe('/upload');
	});

	test('settings link points to /settings', () => {
		render(navigation);
		const link = screen.getByRole('link', { name: /Settings/i });
		expect(link.getAttribute('href')).toBe('/settings');
	});

	test('toggle mode button triggers toggleMode', async () => {
		render(navigation);
		const button = screen.getByRole('button', { name: /Toggle theme/i });
		fireEvent.click(button);
		expect(holder.toggleMode).toHaveBeenCalledTimes(1);
	});
});
