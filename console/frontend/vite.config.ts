import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import react from '@vitejs/plugin-react';
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        home: resolve(__dirname, 'index.html'),
        product: resolve(__dirname, 'product.html'),
        useCases: resolve(__dirname, 'use-cases.html'),
        technology: resolve(__dirname, 'technology.html'),
        docs: resolve(__dirname, 'docs.html'),
        company: resolve(__dirname, 'company.html'),
        contact: resolve(__dirname, 'contact.html'),
        console: resolve(__dirname, 'console.html'),
      },
    },
  },
});
