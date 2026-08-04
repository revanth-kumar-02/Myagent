import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [svelte()],

  resolve: {
    alias: {
      '$lib': path.resolve('./src/lib'),
    },
  },


  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      // Watch the tauri source so hot-reload works
      ignored: ['**/src-tauri/**'],
    },
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    // Produce ES modules that Tauri's WebView understands
    target: process.env.TAURI_PLATFORM === 'windows' ? 'chrome105' : 'safari16',
    minify: process.env.TAURI_DEBUG ? false : true,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
