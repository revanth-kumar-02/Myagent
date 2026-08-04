import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import path from 'path';

export default {
  preprocess: vitePreprocess(),
  kit: undefined, // Not using SvelteKit — plain Svelte SPA
};
