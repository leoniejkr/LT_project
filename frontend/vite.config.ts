import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		tailwindcss()
	],
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
