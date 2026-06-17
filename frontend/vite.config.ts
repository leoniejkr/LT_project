import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		tailwindcss()
	],
	optimizeDeps: {
		exclude: ['@cornerstonejs/dicom-image-loader'],
		include: ['dicom-parser']
	},
	worker: {
		format: 'es'
	},
	server: {
		proxy: {
			'/api': {
				target: 'http://backend:8080',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			}
		}
	}
});
