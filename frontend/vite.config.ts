import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		sveltekit(),
		tailwindcss()
	],
	test: {
		environment: 'jsdom',
		setupFiles: ['./src/test/setup.ts'],
		coverage: {
			provider: 'v8',
			include: [
				'src/lib/**/*.ts',
				'src/lib/components/ui/chat/**/*.svelte',
				'src/lib/components/navigation/**/*.svelte'
			],
			exclude: [
				'src/lib/**/*.test.ts',
				// Typ-/Generierungs-Only-Module ohne ausführbare Logik
				'src/lib/api.ts',
				'src/lib/api-types.ts',
				'src/lib/index.ts'
			],
			thresholds: {
				statements: 80,
				branches: 80,
				functions: 80,
				lines: 80
			}
		}
	},
	resolve: {
		// Nur unter Vitest die zusätzliche 'browser'-Condition setzen; im normalen
		// (Produktions-)Build nichts ueberschreiben, damit die Vite-Defaults gelten.
		...(process.env.VITEST ? { conditions: ['browser'] } : {})
	},
	optimizeDeps: {
		include: []
	},
	worker: {
		format: 'es'
	},
	ssr: {
		noExternal: ['@cornerstonejs/core', '@cornerstonejs/tools']
	},
	server: {
		headers: {
			'Cross-Origin-Embedder-Policy': 'credentialless',
			'Cross-Origin-Opener-Policy': 'same-origin',
		},
		proxy: {
			'/api': {
				target: 'http://backend:8080',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			}
		}
	}
});
