import { beforeEach, describe, expect, test, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/dom';
import navigation from './navigation.svelte';

const { holder } = vi.hoisted(() => ({
	holder: {
		pathname: '/',
		goto: vi.fn(),
		toggleMode: vi.fn(),
	},
}));

vi.mock('$app/state', () => ({
	get page() {
		return { url: new URL(`http://localhost${holder.pathname}`) };
	},
}));

vi.mock('$app/navigation', () => ({
	get goto() {
		return holder.goto;
	},
}));

vi.mock('mode-watcher', () => ({
	toggleMode: () => holder.toggleMode(),
}));

beforeEach(() => {
	holder.pathname = '/';
	holder.goto.mockClear();
	holder.toggleMode.mockClear();
});

describe('navigation.svelte', () => {
	test('renders all three links', () => {
		render(navigation);
		expect(screen.getByText('Home')).toBeTruthy();
		expect(screen.getByText('Upload')).toBeTruthy();
		expect(screen.getByText('Result')).toBeTruthy();
	});

	test('marks Home as active only on the root path', () => {
		holder.pathname = '/';
		const { container } = render(navigation);
		const home = (container.querySelector('button[aria-label]') ??
			screen.getByText('Home').closest('button')) as HTMLButtonElement;
		expect(home.className).toContain('bg-muted');
	});

	test('marks Upload as active on an upload path', () => {
		holder.pathname = '/upload';
		render(navigation);
		const upload = screen.getByText('Upload').closest('button') as HTMLButtonElement;
		expect(upload.className).toContain('bg-muted');
	});

	test('does not mark Home active on subpaths', () => {
		holder.pathname = '/result';
		render(navigation);
		const home = screen.getByText('Home').closest('button') as HTMLButtonElement;
		expect(home.className).not.toContain('bg-muted');
	});

	test('navigates to the result page on click', async () => {
		render(navigation);
		const result = screen.getByText('Result').closest('button') as HTMLButtonElement;
		fireEvent.click(result);
		expect(holder.goto).toHaveBeenCalledWith('/result');
	})

	test('navigates to the upload page on click', async () => {
		render(navigation);
		const upload = screen.getByText('Upload').closest('button') as HTMLButtonElement;
		fireEvent.click(upload);
		expect(holder.goto).toHaveBeenCalledWith('/upload');
	});

	test('settings button navigates to /settings', async () => {
		render(navigation);
		const button = screen.getByRole('button', { name: /Settings/i });
		fireEvent.click(button);
		expect(holder.goto).toHaveBeenCalledWith('/settings');
	});

	test('toggle mode button triggers toggleMode', async () => {
		render(navigation);
		const button = screen.getByRole('button', { name: /Toggle theme/i });
		fireEvent.click(button);
		expect(holder.toggleMode).toHaveBeenCalledTimes(1);
	});
});