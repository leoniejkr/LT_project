import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		tailwindcss()
	],
	optimizeDeps: {
		exclude: [
			'@cornerstonejs/dicom-image-loader',
		],
		include: [
			'dicom-parser',
			'@cornerstonejs/codec-libjpeg-turbo-8bit/decodewasmjs',
			'@cornerstonejs/codec-openjpeg/decodewasmjs',
			'@cornerstonejs/codec-openjph/wasmjs',
			'@cornerstonejs/codec-charls/decodewasmjs'
		]
	},
	worker: {
		format: 'es'
	},
	ssr: {
		noExternal: ['@cornerstonejs/core', '@cornerstonejs/tools', '@cornerstonejs/dicom-image-loader']
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
