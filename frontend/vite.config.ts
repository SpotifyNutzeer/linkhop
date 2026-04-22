import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    // Vite 5.4.x (CVE-2025-30208-Fix) blockt Requests mit 403, wenn der
    // Query-String "://" enthält — genau das, was wir mit ?url=https://…
    // ständig tun. Nur Dev-Server-Check; adapter-static/Nginx ist nicht
    // betroffen.
    fs: { strict: false },
    proxy: {
      '/api': 'http://127.0.0.1:8080'
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    environmentOptions: {
      jsdom: { url: 'http://localhost/' }
    },
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.ts']
  }
});
