import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		sveltekit(),
		tailwindcss()
	],
	test: {
		environment: 'jsdom'
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
