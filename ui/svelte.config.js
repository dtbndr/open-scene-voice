import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// The adapter empties `pages`; that directory holds only build output (the .py files sit one level up).
const output = '../src/scenevoice/web/static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ pages: output, assets: output, fallback: 'index.html', precompress: false, strict: true }),
    paths: { relative: false }
  }
};

export default config;
