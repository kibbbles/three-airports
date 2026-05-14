// @ts-check
import { defineConfig } from 'astro/config';
import { fileURLToPath } from 'url';
import { resolve, dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  site: 'https://kibbbles.github.io',
  base: '/three-airports',
  output: 'static',
  vite: {
    resolve: {
      alias: {
        // import from data/exports/ at build time in Astro frontmatter
        '@data': resolve(__dirname, '../data/exports'),
      },
    },
  },
});
